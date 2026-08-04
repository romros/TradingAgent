import json

from packages.market.bs_probe import _fetch_bs_ohlcv


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({"candles": []}).encode()


def test_bs_audit_never_triggers_dukascopy_fallback(monkeypatch):
    requested = []

    def fake_open(request, timeout):
        requested.append(request.full_url)
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    assert _fetch_bs_ohlcv("http://bs", "MSFT", 25) == {"candles": []}
    assert requested == [
        "http://bs/data/ohlcv/MSFT?tf=1m&limit=25&source=ostium_clean"
    ]
