import json
import math
from urllib.parse import parse_qs, urlparse

from lab.sq_bridge.eurusd_d1_bridge_mapping_v4 import evaluate, fetch_candles


def _m1(start, minutes, *, shift=0.0):
    rows = []
    for index in range(minutes):
        day = index // 900
        within = index % 900
        price = 1.05 + day * .0002 + math.sin(within / 100) * .00005 + shift
        rows.append([start + day * 86400 + within * 60,
                     price, price + .00002, price - .00002, price + .00001, 0])
    return rows


def test_two_leg_bridge_passes_without_requiring_simultaneous_three_way_overlap():
    sq = _m1(1_700_000_000, 6000)
    duka_sq = [row[:] for row in sq]
    duka_mapping = _m1(1_710_000_000, 70 * 900)
    ostium_mapping = _m1(1_710_000_000, 70 * 900, shift=.000001)
    result = evaluate(
        sq_rows=sq, sq_duka_rows=duka_sq,
        mapping_duka_rows=duka_mapping, mapping_ostium_rows=ostium_mapping)
    assert result["decision"] == "PASS_D1_SOURCE_MAPPING"
    assert all(result["checks"].values())
    assert result["sq_dukascopy_bridge"]["common_rows"] == 6000
    assert result["dukascopy_ostium_mapping"]["common_complete_days"] >= 60


def test_price_or_coverage_drift_blocks_mapping():
    sq = _m1(1_700_000_000, 6000)
    duka_sq = [row[:] for row in sq[:4000]]
    duka_mapping = _m1(1_710_000_000, 70 * 900)
    ostium_mapping = _m1(1_710_000_000, 50 * 900, shift=.001)
    result = evaluate(
        sq_rows=sq, sq_duka_rows=duka_sq,
        mapping_duka_rows=duka_mapping, mapping_ostium_rows=ostium_mapping)
    assert result["decision"] == "BLOCK_D1_SOURCE_MAPPING"
    assert result["checks"]["sq_coverage"] is False
    assert result["checks"]["mapping_days"] is False
    assert result["checks"]["close_difference"] is False


def test_fetch_candles_follows_legacy_ostium_offsets(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, timeout):
        assert timeout == 120
        query = parse_qs(urlparse(request.full_url).query)
        offset = int(query.get("offset", [0])[0])
        calls.append(offset)
        pages = {
            0: {"candles": [[100, 1, 1, 1, 1, 0], [160, 2, 2, 2, 2, 0]],
                "next_ts": None, "next_offset": 2},
            2: {"candles": [[220, 3, 3, 3, 3, 0]],
                "next_ts": None, "next_offset": None},
        }
        return Response(pages[offset])

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    rows = fetch_candles("http://broker", "ostium", 100, 280)
    assert calls == [0, 2]
    assert [row[0] for row in rows] == [100, 160, 220]
