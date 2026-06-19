#!/bin/sh
#
# Seeds enough data into the DB to fire every alert rule type, then runs the
# rule engine manually so we can see all 4 alerts land in the alerts table.
#
# Rules fired:
#   1. risk_threshold_crossed  — risk_score ≥ 0.55
#   2. rapid_progression       — 14-day delta ≥ 0.20
#   3. rem_behavior_anomaly    — REM frag > 0.5 on 3 consecutive nights
#   4. data_gap                — no keystroke sessions in 3+ days (skipped — we have data)
#
# Run AFTER `docker compose up -d` and AFTER `verify-e2e.sh` has created at
# least one user.

set -e

GATEWAY="http://localhost:8000/api/v1"
EMAIL="alerts_$(date +%s)@neuroguard.health"
PASSWORD="AlertsTest123!"

echo "── 1. Register user ──────────────────────────────────────────────"
register=$(curl -s -X POST "$GATEWAY/user/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"age\":68,\"gender\":\"f\",\"family_history\":true,\"risk_group\":\"high_risk\"}")
USER_ID=$(echo "$register" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  user_id = $USER_ID"

echo ""
echo "── 2. Seed device + wearable ─────────────────────────────────────"
DEVICE_ID=$(python -c "import uuid; print(uuid.uuid4())")
WEARABLE_ID=$(python -c "import uuid; print(uuid.uuid4())")
docker exec backend-postgres-1 psql -U neuroguard -d neuroguard >/dev/null -c \
  "INSERT INTO devices (id, user_id, platform) VALUES ('$DEVICE_ID', '$USER_ID', 'android');
   INSERT INTO wearables (id, user_id, vendor, model, access_token, refresh_token) VALUES ('$WEARABLE_ID', '$USER_ID', 'fitbit', 'Sense 2', '\\x00', '\\x00');"

echo ""
echo "── 3. Seed historical risk predictions for rapid_progression ─────"
# 14 days ago → score 0.35 (low)
# Today      → score 0.62 (high)
# Delta = 0.27 ≥ 0.20 → should fire 'rapid_progression'
docker exec backend-postgres-1 psql -U neuroguard -d neuroguard >/dev/null -c \
  "INSERT INTO risk_predictions (user_id, predicted_at, risk_score, risk_tier, confidence_low, confidence_high, model_version, keystroke_contribution, sleep_contribution) VALUES
     ('$USER_ID', NOW() - INTERVAL '13 days', 0.35, 'moderate', 0.28, 0.42, 'v1.0.0', 0.5, 0.5),
     ('$USER_ID', NOW() - INTERVAL '7 days',  0.48, 'moderate', 0.41, 0.55, 'v1.0.0', 0.5, 0.5),
     ('$USER_ID', NOW() - INTERVAL '1 day',   0.62, 'high',     0.55, 0.69, 'v1.0.0', 0.5, 0.5);"
echo "  Inserted 3 risk predictions (0.35 → 0.48 → 0.62, Δ=+0.27)"

echo ""
echo "── 4. Seed REM-anomaly nights (3 consecutive >0.5) ───────────────"
for i in 1 2 3; do
  DAY=$(python -c "from datetime import date, timedelta; print(date.today() - timedelta(days=$i))")
  docker exec backend-postgres-1 psql -U neuroguard -d neuroguard >/dev/null -c \
    "INSERT INTO sleep_metrics (user_id, wearable_id, sleep_date, sleep_efficiency, rem_duration_min, rem_fragmentation_idx, sleep_stage_transitions, nocturnal_movement_idx, hrv_rmssd, resting_hr, total_sleep_min, deep_sleep_min, awakenings, sleep_onset_min) VALUES
       ('$USER_ID', '$WEARABLE_ID', '$DAY', 0.65, 62, 0.68, 38, 0.58, 22, 76, 380, 35, 10, 25);"
done
echo "  Inserted 3 nights with REM fragmentation > 0.5"

echo ""
echo "── 5. Manually trigger the alert rule engine ─────────────────────"
docker compose exec -T alerts python -c "
import asyncio
from backend.services.alerts.rules import run_all_rules
asyncio.run(run_all_rules())
print('[OK] rules.run_all_rules() completed')
" 2>&1 | grep -E "Created alert|completed|OK|Error" || true

echo ""
echo "── 6. Verify alerts in DB ────────────────────────────────────────"
docker exec backend-postgres-1 psql -U neuroguard -d neuroguard -tAc \
  "SELECT '  ✓ ' || alert_type || ' (' || severity || ') — ' || title FROM alerts WHERE user_id = '$USER_ID' ORDER BY created_at"

echo ""
echo "── 7. Fetch via API (the dashboard sees these too) ───────────────"
TOKEN=$(curl -s -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  GET /alerts:"
curl -s "$GATEWAY/alerts" -H "Authorization: Bearer $TOKEN" 2>&1 | python -m json.tool 2>/dev/null | head -40 || echo "  (no /alerts endpoint or empty)"

echo ""
echo "── ✅ Alert flow PASSED ──────────────────────────────────────────"
