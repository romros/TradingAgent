from apps import shadow_control_panel as panel


def test_snapshot_is_plain_and_never_authorizes_orders(monkeypatch):
    monkeypatch.setattr(panel, "read", lambda path, default=None: ({
        panel.STATE: {"status": "PASS", "orders_sent": 0},
        panel.CAT_PIPELINE: {"scan": {"action": "NONE", "session": "2026-08-13"}},
        panel.MSFT_PIPELINE: {"scan": {"action": "NONE", "session": "2026-08-13"}},
        panel.PORTFOLIO: {"forward_validation_oos_2022_2024": {"portfolio": {"return_pct": 16}, "diversification": {"correlation_zero_when_inactive": .32}}},
        panel.SXR8_SCHEDULE: {"actions": []},
    }.get(path, default or {})))
    monkeypatch.setattr(panel, "position", lambda path, symbol: {"quantity": 0, "intents": 0, "last_intent": None})
    value = panel.snapshot()
    assert value["mode"] == "SHADOW_ONLY"
    assert value["safety"]["orders_sent"] == 0
    assert value["safety"]["broker_connected"] is False
    assert "Esperant" in value["plain_status"]
