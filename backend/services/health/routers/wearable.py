"""
Wearable endpoints:
  POST /wearable/sync              — manual sleep data ingest (any vendor)
  GET  /wearable/fitbit/connect    — start Fitbit OAuth 2.0 flow
  GET  /wearable/fitbit/callback   — OAuth callback, store encrypted tokens
  POST /wearable/fitbit/sync       — pull latest sleep from Fitbit API
  GET  /wearable/list              — list user's connected wearables
"""

import base64
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.config import get_settings
from ....shared.db.redis import get_redis
from ....shared.db.session import get_db
from ....shared.models.sleep_metrics import SleepMetrics
from ....shared.models.wearable import Wearable
from ....shared.schemas.health import WearableSyncPayload, WearableSyncResponse
from ....shared.security.encryption import encrypt_field, decrypt_field_str as decrypt_field
from ....shared.security.jwt import get_current_user

router   = APIRouter()
settings = get_settings()

# ── Fitbit OAuth constants ────────────────────────────────────────────────────

_FITBIT_AUTH_URL    = "https://www.fitbit.com/oauth2/authorize"
_FITBIT_TOKEN_URL   = "https://api.fitbit.com/oauth2/token"
_FITBIT_SLEEP_URL   = "https://api.fitbit.com/1.2/user/-/sleep/date/{date}.json"
_FITBIT_SCOPE       = "sleep heartrate activity profile"
_OAUTH_STATE_TTL    = 600   # 10 minutes for CSRF state token

# ── Manual sync ────────────────────────────────────────────────────────────────

@router.post("/sync", response_model=WearableSyncResponse)
async def sync_wearable_data(
    payload: WearableSyncPayload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])

    result = await db.execute(
        select(Wearable).where(
            Wearable.id == payload.wearable_id,
            Wearable.user_id == user_id,
            Wearable.is_active == True,
        )
    )
    wearable = result.scalar_one_or_none()
    if not wearable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wearable not found or not active")

    synced, skipped = 0, 0
    for record in payload.sleep_records:
        sleep_date = date.fromisoformat(record.sleep_date)
        existing = await db.execute(
            select(SleepMetrics).where(
                SleepMetrics.user_id == user_id,
                SleepMetrics.sleep_date == sleep_date,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        db.add(SleepMetrics(
            user_id                = user_id,
            wearable_id            = payload.wearable_id,
            sleep_date             = sleep_date,
            sleep_efficiency       = record.sleep_efficiency,
            rem_duration_min       = record.rem_duration_min,
            rem_fragmentation_idx  = record.rem_fragmentation_idx,
            sleep_stage_transitions= record.sleep_stage_transitions,
            nocturnal_movement_idx = record.nocturnal_movement_idx,
            hrv_rmssd              = record.hrv_rmssd,
            resting_hr             = record.resting_hr,
            total_sleep_min        = record.total_sleep_min,
            deep_sleep_min         = record.deep_sleep_min,
            awakenings             = record.awakenings,
            sleep_onset_min        = record.sleep_onset_min,
            raw_stages             = record.raw_stages,
        ))
        synced += 1

    wearable.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return WearableSyncResponse(synced_count=synced, skipped_count=skipped)


# ── Fitbit OAuth — Step 1: redirect ───────────────────────────────────────────

@router.get("/fitbit/connect")
async def fitbit_connect(
    current_user: dict = Depends(get_current_user),
):
    """
    Begin Fitbit OAuth 2.0 Authorization Code flow.
    Returns a redirect to Fitbit's authorization page.
    """
    user_id = current_user["sub"]
    state   = f"{user_id}:{uuid.uuid4().hex}"

    # Store state in Redis for CSRF verification (TTL = 10 min)
    redis = await get_redis()
    await redis.setex(f"fitbit_oauth_state:{state}", _OAUTH_STATE_TTL, user_id)

    params = urlencode({
        "client_id"     : settings.fitbit_client_id,
        "response_type" : "code",
        "scope"         : _FITBIT_SCOPE,
        "redirect_uri"  : settings.fitbit_redirect_uri,
        "state"         : state,
        "expires_in"    : "604800",   # request 7-day access token
    })
    return RedirectResponse(url=f"{_FITBIT_AUTH_URL}?{params}")


# ── Fitbit OAuth — Step 2: callback ───────────────────────────────────────────

@router.get("/fitbit/callback")
async def fitbit_callback(
    code:  str           = Query(...),
    state: str           = Query(...),
    db:    AsyncSession  = Depends(get_db),
):
    """
    Handle Fitbit OAuth callback.  Exchange authorization code for tokens
    and persist them (encrypted) to the wearables table.
    """
    redis = await get_redis()
    stored_user_id = await redis.get(f"fitbit_oauth_state:{state}")
    if not stored_user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis.delete(f"fitbit_oauth_state:{state}")

    user_id = uuid.UUID(stored_user_id)

    # Exchange code for tokens
    credentials = base64.b64encode(
        f"{settings.fitbit_client_id}:{settings.fitbit_client_secret}".encode()
    ).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _FITBIT_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data={
                "client_id"   : settings.fitbit_client_id,
                "grant_type"  : "authorization_code",
                "redirect_uri": settings.fitbit_redirect_uri,
                "code"        : code,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Fitbit token exchange failed")

    tokens = resp.json()
    access_token  = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    expires_in    = int(tokens.get("expires_in", 28800))  # 8 h default

    # Encrypt tokens for storage (AES-256-GCM via shared encryption helper)
    enc_access  = encrypt_field(access_token)
    enc_refresh = encrypt_field(refresh_token)

    # Check for existing Fitbit wearable for this user
    existing = await db.execute(
        select(Wearable).where(
            Wearable.user_id == user_id,
            Wearable.vendor  == "fitbit",
        )
    )
    wearable = existing.scalar_one_or_none()
    if wearable:
        wearable.access_token      = enc_access
        wearable.refresh_token     = enc_refresh
        wearable.token_expires_at  = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        wearable.is_active         = True
    else:
        wearable = Wearable(
            user_id          = user_id,
            vendor           = "fitbit",
            model            = "Fitbit API",
            access_token     = enc_access,
            refresh_token    = enc_refresh,
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            is_active        = True,
        )
        db.add(wearable)

    await db.commit()
    await db.refresh(wearable)

    # Redirect back to mobile deep link / web success page
    return RedirectResponse(url=f"neuroguard://wearable/connected?vendor=fitbit&wearable_id={wearable.id}")


# ── Fitbit Sleep Sync ──────────────────────────────────────────────────────────

@router.post("/fitbit/sync")
async def fitbit_sync(
    days: int            = Query(default=7, ge=1, le=30, description="Number of past days to sync"),
    current_user: dict   = Depends(get_current_user),
    db:  AsyncSession    = Depends(get_db),
):
    """
    Pull sleep data from Fitbit API for the last N days and store it.
    Automatically refreshes the access token if expired.
    """
    user_id = uuid.UUID(current_user["sub"])

    result = await db.execute(
        select(Wearable).where(
            Wearable.user_id == user_id,
            Wearable.vendor  == "fitbit",
            Wearable.is_active == True,
        )
    )
    wearable = result.scalar_one_or_none()
    if not wearable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Fitbit wearable. Connect via GET /wearable/fitbit/connect",
        )

    access_token = await _get_valid_access_token(wearable, db)

    synced, skipped = 0, 0
    async with httpx.AsyncClient(timeout=20) as client:
        for i in range(days):
            target_date = (datetime.now(timezone.utc) - timedelta(days=i)).date()

            # Skip if we already have today's record
            existing = await db.execute(
                select(SleepMetrics).where(
                    SleepMetrics.user_id   == user_id,
                    SleepMetrics.sleep_date == target_date,
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            url = _FITBIT_SLEEP_URL.format(date=target_date.isoformat())
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Fitbit token invalid — please reconnect")
            if resp.status_code == 404 or resp.status_code == 204:
                continue  # no sleep data for this date

            if resp.status_code != 200:
                continue  # skip non-fatal errors and move to next day

            metrics = _parse_fitbit_sleep(resp.json(), user_id, wearable.id, target_date)
            if metrics:
                db.add(metrics)
                synced += 1

    wearable.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return {"synced_count": synced, "skipped_count": skipped, "vendor": "fitbit"}


# ── List wearables ─────────────────────────────────────────────────────────────

@router.get("/list")
async def list_wearables(
    current_user: dict  = Depends(get_current_user),
    db: AsyncSession    = Depends(get_db),
):
    user_id = uuid.UUID(current_user["sub"])
    result  = await db.execute(
        select(Wearable).where(Wearable.user_id == user_id, Wearable.is_active == True)
    )
    wearables = result.scalars().all()
    return [
        {
            "id"            : str(w.id),
            "vendor"        : w.vendor,
            "model"         : w.model,
            "last_synced_at": w.last_synced_at.isoformat() if w.last_synced_at else None,
        }
        for w in wearables
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_valid_access_token(wearable: Wearable, db: AsyncSession) -> str:
    """Decrypt and refresh the Fitbit access token if expired."""
    now = datetime.now(timezone.utc)
    expires_at = wearable.token_expires_at

    # Still valid (with 5 min buffer)
    if expires_at and (expires_at - now).total_seconds() > 300:
        return decrypt_field(wearable.access_token)

    # Refresh
    refresh_token = decrypt_field(wearable.refresh_token)
    credentials   = base64.b64encode(
        f"{settings.fitbit_client_id}:{settings.fitbit_client_secret}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _FITBIT_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to refresh Fitbit token — please reconnect")

    tokens = resp.json()
    new_access  = tokens["access_token"]
    new_refresh = tokens.get("refresh_token", refresh_token)
    expires_in  = int(tokens.get("expires_in", 28800))

    wearable.access_token     = encrypt_field(new_access)
    wearable.refresh_token    = encrypt_field(new_refresh)
    wearable.token_expires_at = now + timedelta(seconds=expires_in)
    await db.flush()  # persist without committing (caller commits)

    return new_access


def _parse_fitbit_sleep(
    data: dict,
    user_id: uuid.UUID,
    wearable_id: uuid.UUID,
    sleep_date: date,
) -> Optional[SleepMetrics]:
    """Parse Fitbit v1.2 sleep response into a SleepMetrics row."""
    summary = data.get("summary", {})
    stages  = summary.get("stages", {})
    sleep   = data.get("sleep", [])

    if not sleep:
        return None

    # Pick the "main" sleep record (longest duration)
    main = max(sleep, key=lambda s: s.get("minutesAsleep", 0), default={})
    if not main:
        return None

    total_min      = float(main.get("minutesAsleep",   0))
    total_in_bed   = float(main.get("timeInBed",       total_min + 30))
    efficiency     = min(total_min / (total_in_bed + 1e-9), 1.0)
    rem_min        = float(stages.get("rem",     0))
    deep_min       = float(stages.get("deep",    0))
    light_min      = float(stages.get("light",   0))
    wake_min       = float(stages.get("wake",    0))
    awakenings     = int(main.get("awakeCount",  0))
    onset_min      = float(main.get("minutesToFallAsleep", 0))

    # Approximate REM fragmentation from transitions in stage data
    level_data = main.get("levels", {}).get("data", [])
    transitions   = _count_stage_transitions(level_data)
    rem_frag_idx  = min(transitions / 20.0, 1.0)  # normalised 0-1

    # Minute-by-minute stage array for raw storage
    raw_stages = [{"t": d.get("dateTime"), "s": d.get("level"), "sec": d.get("seconds")} for d in level_data]

    return SleepMetrics(
        user_id                = user_id,
        wearable_id            = wearable_id,
        sleep_date             = sleep_date,
        sleep_efficiency       = round(efficiency, 3),
        rem_duration_min       = rem_min,
        rem_fragmentation_idx  = round(rem_frag_idx, 3),
        sleep_stage_transitions= transitions,
        nocturnal_movement_idx = None,   # not in Fitbit API v1.2
        hrv_rmssd              = None,   # separate Fitbit HRV endpoint (premium)
        resting_hr             = None,
        total_sleep_min        = total_min,
        deep_sleep_min         = deep_min,
        awakenings             = awakenings,
        sleep_onset_min        = onset_min,
        raw_stages             = raw_stages,
    )


def _count_stage_transitions(level_data: list) -> int:
    """Count the number of sleep-stage transitions in a night."""
    if len(level_data) < 2:
        return 0
    count = 0
    prev_stage = level_data[0].get("level")
    for entry in level_data[1:]:
        stage = entry.get("level")
        if stage and stage != prev_stage:
            count += 1
            prev_stage = stage
    return count


# ── CSV / manual bulk import (Mi Fitness, Zepp, Samsung Health exports) ────────

from pydantic import BaseModel, Field


class ImportSleepRecord(BaseModel):
    """One night of sleep, already normalised by the frontend column-mapper."""
    sleep_date:             str                       # ISO yyyy-mm-dd
    total_sleep_min:        Optional[float] = None
    deep_sleep_min:         Optional[float] = None
    rem_duration_min:       Optional[float] = None
    sleep_efficiency:       Optional[float] = None     # 0-1
    rem_fragmentation_idx:  Optional[float] = None     # 0-1
    sleep_stage_transitions: Optional[int]  = None
    nocturnal_movement_idx: Optional[float] = None
    hrv_rmssd:              Optional[float] = None
    resting_hr:             Optional[float] = None
    awakenings:             Optional[int]   = None
    sleep_onset_min:        Optional[float] = None


class ImportSleepPayload(BaseModel):
    vendor:  str = Field(default="xiaomi")
    model:   str = Field(default="Mi Fitness import")
    records: list[ImportSleepRecord]


class ImportSleepResponse(BaseModel):
    synced_count:  int
    skipped_count: int
    derived_count: int   # records where REM/efficiency were estimated, not measured
    wearable_id:   str
    warnings:      list[str]


@router.post("/import", response_model=ImportSleepResponse)
async def import_sleep_csv(
    payload: ImportSleepPayload,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk-import sleep nights from a wearable data export (Mi Fitness, Zepp, etc.).

    The frontend parses the CSV and maps columns, so this endpoint receives clean
    JSON.  Missing fields that the ML model needs (REM fragmentation, efficiency)
    are *estimated* from the fields we do have so the model still gets a usable
    35-feature vector — with a warning so the clinician knows it's derived.
    """
    user_id = uuid.UUID(current_user["sub"])

    # Find or create a wearable row for this import source
    result = await db.execute(
        select(Wearable).where(
            Wearable.user_id == user_id,
            Wearable.vendor  == payload.vendor,
        )
    )
    wearable = result.scalar_one_or_none()
    if not wearable:
        wearable = Wearable(
            user_id       = user_id,
            vendor        = payload.vendor,
            model         = payload.model,
            access_token  = b"\x00",   # not OAuth — CSV import has no token
            refresh_token = b"\x00",
            is_active     = True,
        )
        db.add(wearable)
        await db.flush()

    synced = skipped = derived = 0
    warnings: list[str] = []
    _derived_field_counts: dict[str, int] = {}

    for rec in payload.records:
        try:
            sleep_date = date.fromisoformat(rec.sleep_date[:10])
        except (ValueError, TypeError):
            warnings.append(f"Skipped row with invalid date: {rec.sleep_date!r}")
            continue

        existing = await db.execute(
            select(SleepMetrics).where(
                SleepMetrics.user_id == user_id,
                SleepMetrics.sleep_date == sleep_date,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        total = rec.total_sleep_min
        deep  = rec.deep_sleep_min

        # ── Derive the features the model needs but the export may lack ──────
        # Track WHICH fields were estimated so the warning is accurate.
        derived_fields: list[str] = []

        efficiency = rec.sleep_efficiency
        if efficiency is None and total:
            # Assume ~30 min awake in bed if not reported (typical for budget trackers)
            efficiency = round(total / (total + 30.0), 3)
            derived_fields.append("sleep_efficiency")

        rem = rec.rem_duration_min
        if rem is None and total:
            # Healthy REM ≈ 20-25% of total sleep — use 22% as a neutral prior
            rem = round(total * 0.22, 1)
            derived_fields.append("rem_duration")

        rem_frag = rec.rem_fragmentation_idx
        if rem_frag is None:
            # Estimate from awakenings if available, else neutral 0.3
            if rec.awakenings is not None:
                rem_frag = round(min(rec.awakenings / 15.0, 1.0), 3)
            else:
                rem_frag = 0.3
            derived_fields.append("rem_fragmentation")

        if derived_fields:
            derived += 1
            for fld in derived_fields:
                _derived_field_counts[fld] = _derived_field_counts.get(fld, 0) + 1

        db.add(SleepMetrics(
            user_id                 = user_id,
            wearable_id             = wearable.id,
            sleep_date              = sleep_date,
            sleep_efficiency        = efficiency,
            rem_duration_min        = rem,
            rem_fragmentation_idx   = rem_frag,
            sleep_stage_transitions = rec.sleep_stage_transitions,
            nocturnal_movement_idx  = rec.nocturnal_movement_idx,
            hrv_rmssd               = rec.hrv_rmssd,
            resting_hr              = rec.resting_hr,
            total_sleep_min         = total,
            deep_sleep_min          = deep,
            awakenings              = rec.awakenings,
            sleep_onset_min         = rec.sleep_onset_min,
        ))
        synced += 1

    wearable.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    if _derived_field_counts:
        _labels = {
            "sleep_efficiency": "sleep efficiency",
            "rem_duration":     "REM duration",
            "rem_fragmentation":"REM fragmentation index",
        }
        parts = [
            f"{_labels.get(f, f)} estimated for {c} night(s)"
            for f, c in sorted(_derived_field_counts.items())
        ]
        warnings.append(
            "Some fields weren't in this export and were estimated: "
            + "; ".join(parts)
            + ". All other fields (e.g. total/deep/REM duration, resting HR) are "
              "real measurements where present."
        )

    return ImportSleepResponse(
        synced_count  = synced,
        skipped_count = skipped,
        derived_count = derived,
        wearable_id   = str(wearable.id),
        warnings      = warnings,
    )
