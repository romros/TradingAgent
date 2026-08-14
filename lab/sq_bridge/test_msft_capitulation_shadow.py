import csv, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_signal_creates_atomic_round_trip_and_is_idempotent(tmp_path):
    candles=tmp_path/'m.csv'; ledger=tmp_path/'ledger.json'
    with candles.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['date','open','high','low','close']);w.writeheader()
        for day in range(1,20): w.writerow(dict(date=f'2024-01-{day:02d}',open=100,high=101,low=99,close=100))
        w.writerow(dict(date='2024-01-20',open=100,high=100,low=89,close=90))
        w.writerow(dict(date='2024-01-21',open=91,high=94,low=90,close=93))
    cmd=[sys.executable,str(ROOT/'apps/msft_capitulation_shadow_daily.py'),'--candles',str(candles),'--ledger',str(ledger),'--session','2024-01-21','--capital','1000']
    first=json.loads(subprocess.run(cmd,text=True,capture_output=True,check=True).stdout)
    second=json.loads(subprocess.run(cmd,text=True,capture_output=True,check=True).stdout)
    assert first['action']=='BUY_AND_SELL' and first['intents_created']==2
    assert second['intents_created']==0
    value=json.loads(ledger.read_text()); assert [x['action'] for x in value['intents']]==['BUY','SELL']
    assert ledger.with_suffix('.csv').exists()
