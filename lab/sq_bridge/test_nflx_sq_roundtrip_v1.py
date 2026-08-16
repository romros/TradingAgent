from pathlib import Path
from lab.sq_bridge.nflx_sq_roundtrip_v1 import audit
def test_roundtrip_compares_dates_and_ohlc_not_volume(tmp_path):
 a=tmp_path/'a.csv';b=tmp_path/'b.csv';row='2024.01.02,00:00,1.000000,2.000000,0.500000,1.500000,10\n';a.write_text(row*1995);b.write_text(row.replace(',10\n',',9\n')*1995);r=audit(a,b);assert r['decision'].startswith('PASS');assert not r['volume_parity_required']
