import json
import zipfile

import pytest

from lab.sq_bridge.sqx_monte_carlo_materialize import materialize, verify_manifest
from lab.sq_bridge.test_sqx_monte_carlo_contract import _sqx


def test_materializes_reproducible_source_bound_sqx_per_native_run(tmp_path):
    source = _sqx(tmp_path, count=4)
    # Add the members required by orderstocsv.
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("settings.xml", "settings")
        archive.writestr("strategy_Portfolio.xml", "strategy")
        archive.writestr("version.txt", "3")
    first_dir = tmp_path / "first"
    result = materialize(source, first_dir, simulations=4,
                         probability_pct=10, max_change_pct=10)
    assert len(result["runs"]) == 4
    assert verify_manifest(first_dir / "materialization.manifest.json") == result
    assert materialize(source, first_dir, simulations=4,
                       probability_pct=10, max_change_pct=10) == result
    with zipfile.ZipFile(result["runs"][2]["materialized_sqx_path"]) as archive:
        assert archive.read("orders.bin") == b"orders-2"
    second_dir = tmp_path / "second"
    again = materialize(source, second_dir, simulations=4,
                        probability_pct=10, max_change_pct=10)
    assert [row["materialized_sqx_sha256"] for row in result["runs"]] == [
        row["materialized_sqx_sha256"] for row in again["runs"]]


def test_materialization_manifest_detects_generated_sqx_tampering(tmp_path):
    source = _sqx(tmp_path, count=4)
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("settings.xml", "settings")
        archive.writestr("strategy_Portfolio.xml", "strategy")
        archive.writestr("version.txt", "3")
    result = materialize(source, tmp_path / "out", simulations=4,
                         probability_pct=10, max_change_pct=10)
    target = result["runs"][0]["materialized_sqx_path"]
    with open(target, "ab") as handle:
        handle.write(b"changed")
    with pytest.raises(ValueError, match="LINEAGE"):
        verify_manifest(tmp_path / "out" / "materialization.manifest.json")
