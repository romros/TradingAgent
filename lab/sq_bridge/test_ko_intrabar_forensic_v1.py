import json
from pathlib import Path
from lab.sq_bridge.ko_intrabar_forensic_v1 import run

ROOT=Path(__file__).resolve().parents[2]
def test_entry_precedes_target_by_more_than_six_hours():
 r=run(ROOT/'data/ibkr_sq_v2/dukascopy_m1/KOUSUSD/_daily_cache/year=2022/month=11/day=30.csv.gz')
 assert r['decision']=='PASS_ENTRY_PRECEDES_TARGET'
 assert r['rth_minutes']==390
 assert r['target']['minutes_after_entry']==380


def test_ko_oos_fails_the_frozen_economic_gate():
 audit=json.loads((ROOT/'data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/ko_oos_2024/0_242_v2/small_account_audit.json').read_text())
 for capital in ('1000','2000','3000'):
  assert audit['results'][capital]['stress']['trades']==14
  assert audit['results'][capital]['stress']['return_pct']<0
  assert audit['results'][capital]['stress']['profit_factor']<1
