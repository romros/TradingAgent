import json
from pathlib import Path

from lab.sq_bridge.crypto_h4_market_preflight_v4 import compose


ROOT = Path(__file__).resolve().parents[2]


def test_live_crypto_preflights_fail_closed_without_performance_access():
    for market in ("btcusd", "ethusd"):
        result = compose(ROOT / "lab" / "sq_bridge" /
                         f"{market}_h4_market_preflight_v4_config.json")
        assert result["decision"] == "BLOCK"
        assert result["research_authorized"] is False
        assert result["performance_accessed"] is False
        assert result["holdout_accessed"] is False
        assert result["sqcli_authorized"] is False
        assert result["candidate_ids"] == []
        assert result["blocking_reasons"] == [
            "CRYPTO_PROXY_MAPPING_NOT_MATURE",
            "OSTIUM_200_USDC_COSTS_NOT_FROZEN",
        ]


def test_tampered_sq_export_is_rejected(tmp_path):
    config_path = ROOT / "lab" / "sq_bridge" / "btcusd_h4_market_preflight_v4_config.json"
    config = json.loads(config_path.read_text())
    resource_path = ROOT / "lab" / "sq_bridge" / config["sq_resource"]
    resource = json.loads(resource_path.read_text())
    resource["roundtrip"]["export_sha256"] = "0" * 64
    fake_resource = tmp_path / "resource.json"
    fake_resource.write_text(json.dumps(resource))
    config["canonical_source"] = str((ROOT / "lab" / "sq_bridge" /
                                      config["canonical_source"]).resolve())
    config["mapping"] = str((ROOT / "lab" / "sq_bridge" / config["mapping"]).resolve())
    config["costs"] = str((ROOT / "lab" / "sq_bridge" / config["costs"]).resolve())
    config["preregistration"] = str((ROOT / "lab" / "sq_bridge" /
                                     config["preregistration"]).resolve())
    config["sq_resource"] = str(fake_resource)
    fake_config = tmp_path / "config.json"
    fake_config.write_text(json.dumps(config))
    result = compose(fake_config)
    assert "SQ_H4_RESOURCE_NOT_PROVEN" in result["blocking_reasons"]
    assert result["research_authorized"] is False
