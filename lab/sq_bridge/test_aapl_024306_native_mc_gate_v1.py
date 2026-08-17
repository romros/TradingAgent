import struct

import pytest

from lab.sq_bridge.aapl_024306_native_mc_gate_v1 import compact_pnls, percentile


def test_decodes_compact_native_pnls():
    payload = struct.pack(">4i", 3, 675, -535, 140)
    assert compact_pnls(payload) == [6.75, -5.35, 1.4]


def test_rejects_count_mismatch():
    with pytest.raises(ValueError, match="count mismatch"):
        compact_pnls(struct.pack(">2i", 2, 100))


def test_linear_percentile():
    assert percentile([0, 10, 20], .25) == 5
