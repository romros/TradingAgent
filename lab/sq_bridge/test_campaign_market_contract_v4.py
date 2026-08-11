import pytest

from lab.sq_bridge.campaign_market_contract_v4 import (
    instrument_identity, validate,
)


def _config():
    return {"market": {
        "symbol": "EURUSD", "timeframe": "D1",
        "source_timezone": "Etc/UTC", "ostium_pair_id": "2",
        "ostium_pair_from": "EUR", "ostium_pair_to": "USD",
        "ostium_category": "forex"}}


def test_market_contract_normalizes_identity():
    market = validate(_config())
    assert instrument_identity(market) == ("2", "EUR", "USD", "forex")


@pytest.mark.parametrize("key,value", [
    ("symbol", "eurusd"), ("timeframe", "D0"),
    ("ostium_pair_id", "pair-2"), ("ostium_category", "metal"),
])
def test_market_contract_rejects_ambiguous_identifiers(key, value):
    config = _config()
    config["market"][key] = value
    with pytest.raises(ValueError, match="contract invalid"):
        validate(config)


def test_market_contract_is_mandatory():
    with pytest.raises(ValueError, match="contract missing"):
        validate({})


def test_market_contract_rejects_unknown_timezone():
    config = _config()
    config["market"]["source_timezone"] = "Mars/Olympus"
    with pytest.raises(ValueError, match="timezone invalid"):
        validate(config)
