from lab.sq_bridge.pep_train_representatives_v1 import select


def test_selection_is_pareto_and_structurally_unique():
    rows = []
    for index in range(7):
        rows.append({
            "strategy": f"S{index}", "file": f"S{index}.sqx",
            "sqx_sha256": str(index), "structural_family_sha256": f"f{index // 2}",
            "entry_indicator_archetype_sha256": f"e{index // 2}", "trades": 30,
            "profit": 100 - index, "drawdown": 20,
            "profit_drawdown_ratio": 5 - index / 10, "fitness": 1,
            "complexity": 2, "entry_indicator_types": []})
    result = select({"pareto_candidates": [row["strategy"] for row in rows],
                     "candidates": rows, "source_inventory_sha256": "x"})
    assert result["selected_count"] == 4
    assert len({row["structural_family_sha256"]
                for row in result["selected"]}) == 4
