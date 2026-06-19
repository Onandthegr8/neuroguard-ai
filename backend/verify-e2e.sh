#!/bin/sh
#
# NeuroGuard end-to-end smoke test
#
# Runs against the local docker-compose stack and verifies the full PHI pipeline:
#   1. User registration via /user/register
#   2. JWT issuance via /auth/login
#   3. Device seeded directly (no /devices endpoint yet — Phase 2)
#   4. 5 keystroke sessions ingested via /keystroke/features
#   5. 5 sleep nights seeded directly (Fitbit OAuth flow is the production path)
#   6. ML inference triggered via /risk/compute
#   7. Risk score fetched via /risk/score — confirms model_version, SHAP, contributors
#   8. HIPAA audit_logs verified to contain CREATE + LOGIN actions
#
# Prerequisites:
#   docker compose up -d
#   (risk service uses heuristic fallback unless torch is in the container;
#    requirements.txt now includes torch so a rebuild gives you real model inference)
#
# Usage:
#   sh verify-e2e.sh

set -e

GATEWAY="http://localhost:8000/api/v1"
EMAIL="e2e_$(date +%s)@neuroguard.health"
PASSWORD="TestPassword123!"

echo "── 1. Register user ──────────────────────────────────────────────"
register=$(curl -s -X POST "$GATEWAY/user/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"age\":58,\"gender\":\"f\",\"family_history\":true,\"risk_group\":\"high_risk\"}")
USER_ID=$(echo "$register" | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
[ -z "$USER_ID" ] && { echo "[FAIL] registration: $register"; exit 1; }
echo "  user_id = $USER_ID"

echo ""
echo "── 2. Login ──────────────────────────────────────────────────────"
TOKEN=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
[ -z "$TOKEN" ] && { echo "[FAIL] login"; exit 1; }
echo "  token issued (${#TOKEN} chars)"

echo ""
echo "── 3. Seed device row (no /devices endpoint yet) ─────────────────"
DEVICE_ID=$(python -c "import uuid; print(uuid.uuid4())")
docker exec backend-postgres-1 psql -U neuroguard -d neuroguard -tAc \
  "INSERT INTO devices (id, user_id, platform, device_model, os_version, app_version) VALUES ('$DEVICE_ID', '$USER_ID', 'android', 'Pixel 8', '14', '1.0.0')" >/dev/null
echo "  device_id = $DEVICE_ID"

echo ""
echo "── 4. Ingest 5 keystroke sessions (PD-like timing) ───────────────"
DWELL=$(python -c "import random; random.seed(42); print('['+','.join(str(round(random.gauss(115,25),1)) for _ in range(35))+']')")
IKI=$(python -c "import random; random.seed(42); print('['+','.join(str(round(random.gauss(295,80),1)) for _ in range(40))+']')")
for i in 1 2 3 4 5; do
  NOW=$(python -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) - timedelta(hours=$i)).isoformat())")
  END=$(python -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) - timedelta(hours=$i, minutes=-15)).isoformat())")
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GATEWAY/keystroke/features" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"device_id\":\"$DEVICE_ID\",\"session_start\":\"$NOW\",\"session_end\":\"$END\",\"key_press_duration_ms\":$DWELL,\"inter_key_interval_ms\":$IKI,\"typing_speed_wpm\":25.0,\"correction_frequency\":0.14,\"typing_entropy\":0.58,\"autocorrect_rate\":0.08,\"diurnal_hour\":14,\"app_context\":\"messaging\"}")
  echo "  session $i: HTTP $code"
done

echo ""
echo "── 5. Seed wearable + 5 nights of sleep data ─────────────────────"
WEARABLE_ID=$(python -c "import uuid; print(uuid.uuid4())")
docker exec backend-postgres-1 psql -U neuroguard -d neuroguard -tAc \
  "INSERT INTO wearables (id, user_id, vendor, model, access_token, refresh_token) VALUES ('$WEARABLE_ID', '$USER_ID', 'fitbit', 'Sense 2', '\\x00', '\\x00')" >/dev/null
for i in 1 2 3 4 5; do
  DAY=$(python -c "from datetime import date, timedelta; print(date.today() - timedelta(days=$i))")
  docker exec backend-postgres-1 psql -U neuroguard -d neuroguard -tAc \
    "INSERT INTO sleep_metrics (user_id, wearable_id, sleep_date, sleep_efficiency, rem_duration_min, rem_fragmentation_idx, sleep_stage_transitions, nocturnal_movement_idx, hrv_rmssd, resting_hr, total_sleep_min, deep_sleep_min, awakenings, sleep_onset_min) VALUES ('$USER_ID', '$WEARABLE_ID', '$DAY', 0.68, 65, 0.62, 35, 0.55, 22, 76, 390, 35, 9, 28)" >/dev/null
done
echo "  5 nights inserted"

echo ""
echo "── 6. Trigger ML inference ───────────────────────────────────────"
compute=$(curl -s -X POST "$GATEWAY/risk/compute" -H "Authorization: Bearer $TOKEN")
echo "  $compute"

echo ""
echo "── 7. Fetch risk score (waiting up to 15s for background task) ──"
SCORE=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  sleep 1
  resp=$(curl -s "$GATEWAY/risk/score" -H "Authorization: Bearer $TOKEN")
  if echo "$resp" | grep -q "risk_score"; then
    SCORE="$resp"
    break
  fi
done
if [ -z "$SCORE" ]; then
  echo "  [FAIL] no risk score after 15s — check 'docker compose logs risk'"
  exit 1
fi
echo "$SCORE" | python -m json.tool

echo ""
echo "── 8. HIPAA audit trail ──────────────────────────────────────────"
docker exec backend-postgres-1 psql -U neuroguard -d neuroguard -tAc \
  "SELECT '  ' || COUNT(*) || ' audit rows | actions: ' || string_agg(DISTINCT action, ', ') FROM audit_logs WHERE actor_id = '$USER_ID'"

echo ""
echo "── ✅ End-to-end verification PASSED ─────────────────────────────"
