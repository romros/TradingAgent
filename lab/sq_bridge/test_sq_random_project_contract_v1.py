import json
from pathlib import Path
from lab.sq_bridge.sq_random_project_contract_v1 import verify

ROOT=Path(__file__).resolve().parents[2]
def test_source_and_sq_import_have_same_scientific_contract():
 base=ROOT/'data/ibkr_sq_v2/goog_d1_capitulation_pilot';manifest=json.loads((base/'project.manifest.json').read_text())
 source=verify(base/'project.cfx',manifest)
 imported=verify(base/'sq_imported_project_confirmed.cfx',manifest)
 assert source==imported
 assert imported['minimum_trades']=='40'
 assert imported['minimum_profit_factor']=='1.08'
