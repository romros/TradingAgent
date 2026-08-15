import csv
from pathlib import Path
from sgln_sq_d1_source_v1 import convert

ROOT=Path(__file__).resolve().parents[2]
def test_gbp_conversion_and_boundary(tmp_path):
    source=ROOT/'data/ibkr_sq_v2/preflight/SGLN_L_ADJUSTED_D1_through_2024.csv'
    output=tmp_path/'x.csv'; receipt=tmp_path/'x.json'; result=convert(source,output,receipt)
    rows=list(csv.reader(output.open()))
    assert result['last'] < '2025.01.01' and result['scale'] == .01
    assert 10 < float(rows[0][2]) < 100
    assert len(rows) == result['rows']
