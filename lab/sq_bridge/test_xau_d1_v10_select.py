from lab.sq_bridge.xau_d1_v10_select import adjacent, components, medoid


GRID = {"side": ["long", "short"], "trend_ema": [100, 200], "rsi_period": [2, 3, 5],
        "rsi_extreme": [5, 10, 15], "stop_atr": [1., 1.5, 2.], "hold_sessions": [1, 2, 3]}


def row(candidate, **changes):
    params = {"side": "long", "trend_ema": 100, "rsi_period": 2,
              "rsi_extreme": 10, "stop_atr": 1., "hold_sessions": 1}
    params.update(changes)
    return {"candidate_id": candidate, "parameters": params}


def test_adjacency_requires_exactly_one_orthogonal_grid_step():
    assert adjacent(row("a")["parameters"], row("b", stop_atr=1.5)["parameters"], GRID)
    assert not adjacent(row("a")["parameters"], row("b", side="short")["parameters"], GRID)
    assert not adjacent(row("a")["parameters"], row("b", stop_atr=1.5, hold_sessions=2)["parameters"], GRID)


def test_medoid_is_centre_of_a_three_node_path():
    rows = [row("a", stop_atr=1.), row("b", stop_atr=1.5), row("c", stop_atr=2.)]
    group = components(rows, GRID)[0]
    assert rows[medoid(group, rows, GRID)]["candidate_id"] == "b"
