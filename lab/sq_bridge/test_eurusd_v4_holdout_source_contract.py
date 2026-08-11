import hashlib
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).parent


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_uses_roundtripped_v3_source_ending_at_frozen_holdout():
    config = json.loads((ROOT / "eurusd_v4_sq_worker_config.json").read_text())
    registry_path = ROOT / config["registry_path"]
    assert _sha(registry_path) == config["registry_sha256"]
    registry = json.loads(registry_path.read_text())
    market = registry["markets"]["EURUSD"]
    assert market["sq_symbol"] == "EURUSD_ALQ_NY17_D1_V3"
    assert int(market["sq_resource_attributes"]["dateTo"]) == 1785456000000

    contract_path = ROOT / config["small_account_candle_contract_path"]
    assert _sha(contract_path) == config["small_account_candle_contract_sha256"]
    contract = json.loads(contract_path.read_text())
    assert contract["decision"] == "PASS_CANDLE_PARITY"
    assert contract["sq_rows"] == contract["dukascopy_rows"] == 5993
    assert contract["ohlc_match_pct"] == 100
    last = date.fromisoformat(contract["last_common_timestamp_utc"][:10])
    assert last == date(2026, 7, 31)

    audit = json.loads((ROOT / "evidence/eurusd_alq_ny17_d1_resource_audit_v4_v3.json").read_text())
    assert audit["decision"] == "PASS_SQ_D1_RESOURCE"
    assert audit["checks"]["holdout_covered"] is True
    assert audit["symbol"] == market["sq_symbol"]
