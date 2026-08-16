from lab.sq_bridge.select_structural_representatives_v1 import select


def test_selects_medoid_from_repeated_family_only():
    candidates = [
        {"strategy": "a", "sqx_sha256": "a", "trades": 10, "profit_drawdown_ratio": 1, "complexity": 2},
        {"strategy": "b", "sqx_sha256": "b", "trades": 20, "profit_drawdown_ratio": 2, "complexity": 3},
        {"strategy": "c", "sqx_sha256": "c", "trades": 30, "profit_drawdown_ratio": 3, "complexity": 4},
        {"strategy": "solo", "sqx_sha256": "s", "trades": 99, "profit_drawdown_ratio": 9, "complexity": 1},
    ]
    inventory = {"source_inventory_sha256": "i", "candidates": candidates,
                 "families": [{"structural_family_sha256": "f", "count": 3,
                               "members": ["a", "b", "c"]},
                              {"structural_family_sha256": "s", "count": 1,
                               "members": ["solo"]}]}
    result = select(inventory)
    assert [row["candidate_id"] for row in result["representatives"]] == ["b"]
    assert result["selection_uses_validation"] is False
