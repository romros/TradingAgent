#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_DIR=${FOMC_SOURCE_DIR:-$ROOT/lab/out/market_sources/fomc_official}
MANIFEST=${FOMC_MANIFEST:-$ROOT/lab/sq_bridge/evidence/fomc_regular_statement_calendar_2015_2026.json}
CSV=${FOMC_CSV:-$SOURCE_DIR/fomc_regular_statement_calendar_2015_2026.csv}
BASE=https://www.federalreserve.gov/monetarypolicy

mkdir -p "$SOURCE_DIR"
for YEAR in 2015 2016 2017 2018 2019 2020; do
  curl -L --fail --max-time 30 "$BASE/fomchistorical${YEAR}.htm" \
    -o "$SOURCE_DIR/fomchistorical${YEAR}.htm"
done
curl -L --fail --max-time 30 "$BASE/fomccalendars.htm" -o "$SOURCE_DIR/fomccalendars.htm"
curl -L --fail --max-time 30 "$BASE/fomcpresconf20150318.htm" \
  -o "$SOURCE_DIR/fomcpresconf20150318.htm"
curl -L --fail --max-time 30 "$BASE/fomcpresconf20250319.htm" \
  -o "$SOURCE_DIR/fomcpresconf20250319.htm"

python3 "$ROOT/lab/sq_bridge/fomc_statement_calendar.py" \
  --root "$SOURCE_DIR" --manifest "$MANIFEST" --csv "$CSV"
