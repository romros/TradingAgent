#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SCHEDULE=${FOMC_SCHEDULE_FILE:-$ROOT/lab/sq_bridge/evidence/fomc_upcoming_schedule_asof_20260810.json}
EVENT_DATE=${FOMC_EVENT_DATE:-$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next_scheduled_decision_date"])' "$SCHEDULE")}
case "$EVENT_DATE" in
  20[0-9][0-9]-[01][0-9]-[0-3][0-9]) ;;
  *) echo "INVALID_FOMC_EVENT_DATE=$EVENT_DATE" >&2; exit 2 ;;
esac

YEAR=$(printf '%s' "$EVENT_DATE" | cut -d- -f1)
MONTH=$(printf '%s' "$EVENT_DATE" | cut -d- -f2 | sed 's/^0//')
DAY=$(printf '%s' "$EVENT_DATE" | cut -d- -f3 | sed 's/^0//')
DATA_DIR="$ROOT/data/ostium_event_economics/fomc_$EVENT_DATE"
LOG="$DATA_DIR/collector.log"
LOCK="/tmp/tradingagent-ostium-fomc-$EVENT_DATE.lock"
MARKER="# tradingagent-ostium-fomc-event-$EVENT_DATE"
# Cron selects month/day; the wrapper also checks the year and exact NY event window.
LINE="* * $DAY $MONTH * flock -n $LOCK env FOMC_EVENT_DATE=$EVENT_DATE $ROOT/scripts/capture_ostium_fomc_event_economics.sh >> $LOG 2>&1 $MARKER"

mkdir -p "$DATA_DIR"
CURRENT=$(crontab -l 2>/dev/null || true)
if printf '%s\n' "$CURRENT" | grep -Fq "$MARKER"; then
  echo "already installed for $EVENT_DATE"
  exit 0
fi
{
  printf '%s\n' "$CURRENT"
  printf '%s\n' "$LINE"
} | crontab -
echo "installed_event_date=$EVENT_DATE expected_year=$YEAR"
echo "$LINE"
