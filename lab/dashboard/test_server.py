from lab.dashboard import server


def test_snapshot_reports_two_edge_shadow_portfolio_without_authority(monkeypatch):
    monkeypatch.setattr(server, "docker_usage", lambda: {"available": False})
    value = server.snapshot()

    assert value["instrument"] == "SXR8 + CAT"
    assert value["crypto_allowed"] is False
    assert value["paper_authorized"] is False
    assert value["live_authorized"] is False
    assert len(value["universe"]) == 13
    assert {row["symbol"] for row in value["universe"]} >= {"CAT", "MSFT", "TSLA"}
    assert all(row["symbol"] != "IBUS500" for row in value["universe"])
    assert {row["status"] for row in value["candidates"]} == {
        "SHADOW_PAPER_READY", "RESEARCH_SHADOW"}
    assert value["portfolios"][0]["status"] == "TWO_EDGE_SHADOW_PORTFOLIO"
    assert value["portfolios"][0]["correlation"] < .5
    assert any("2025+ segellat" in finding for finding in value["findings"])
