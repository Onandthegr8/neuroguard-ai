import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class KeystrokePayload(BaseModel):
    device_id: uuid.UUID
    session_start: datetime
    session_end: datetime
    key_press_duration_ms: List[float] = Field(default_factory=list)
    inter_key_interval_ms: List[float] = Field(default_factory=list)
    typing_speed_wpm: Optional[float] = None
    correction_frequency: Optional[float] = None
    typing_entropy: Optional[float] = None
    autocorrect_rate: Optional[float] = None
    diurnal_hour: Optional[int] = Field(None, ge=0, le=23)
    app_context: Optional[str] = Field(None, max_length=30)

    @field_validator("app_context")
    @classmethod
    def sanitize_app_context(cls, v: Optional[str]) -> Optional[str]:
        if v:
            allowed = {"messaging", "email", "notes", "browser", "other"}
            return v if v in allowed else "other"
        return v


class KeystrokeIngestResponse(BaseModel):
    session_id: uuid.UUID
    quality_score: float


class SleepRecord(BaseModel):
    sleep_date: str  # ISO date string
    sleep_efficiency: Optional[float] = None
    rem_duration_min: Optional[float] = None
    rem_fragmentation_idx: Optional[float] = None
    sleep_stage_transitions: Optional[int] = None
    nocturnal_movement_idx: Optional[float] = None
    hrv_rmssd: Optional[float] = None
    resting_hr: Optional[float] = None
    total_sleep_min: Optional[float] = None
    deep_sleep_min: Optional[float] = None
    awakenings: Optional[int] = None
    sleep_onset_min: Optional[float] = None
    raw_stages: Optional[dict] = None


class WearableSyncPayload(BaseModel):
    wearable_id: uuid.UUID
    sleep_records: List[SleepRecord]


class WearableSyncResponse(BaseModel):
    synced_count: int
    skipped_count: int


class HealthSummaryResponse(BaseModel):
    wellness_score: int = Field(ge=0, le=100)
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_tier: str
    sleep_quality_last_night: Optional[float]
    typing_stability_7d: Optional[float]
    wearable_sync_status: str
    data_completeness: float
    last_updated: datetime
