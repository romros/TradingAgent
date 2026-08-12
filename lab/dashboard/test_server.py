from lab.dashboard import server


def test_snapshot_reports_only_clean_slate_v2(monkeypatch):
    monkeypatch.setattr(server, "docker_usage", lambda: {"available": False})
    value = server.snapshot()

    assert value["instrument"] == "13 actius v2"
    assert value["crypto_allowed"] is False
    assert value["paper_authorized"] is False
    assert value["live_authorized"] is False
    assert len(value["universe"]) == 13
    assert {row["symbol"] for row in value["universe"]} >= {"CAT", "MSFT", "TSLA"}
    assert all(row["symbol"] != "IBUS500" for row in value["universe"])
    assert any("163" in finding for finding in value["findings"])
    assert value["candidates"] == []
    assert value["portfolios"] == []
