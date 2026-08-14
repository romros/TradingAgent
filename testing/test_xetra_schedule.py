import datetime as dt,json,subprocess,sys
from pathlib import Path
SCRIPT=Path(__file__).parents[1]/'lab/sq_bridge/build_xetra_turn_of_month_schedule.py'
def test_official_closed_days_excluded_and_august_cycle(tmp_path):
 source=Path(__file__).parents[1]/'lab/sq_bridge/xetra_calendar_2026.json';out=tmp_path/'out.json';subprocess.run([sys.executable,str(SCRIPT),'--calendar',str(source),'--output',str(out)],check=True,capture_output=True);r=json.loads(out.read_text());actions={(x['date'],x['action']) for x in r['actions']};assert ('2026-08-31','BUY') in actions and ('2026-09-04','SELL') in actions and r['sessions']==254
