from lab.sq_bridge.xau_d1_v10_validation import passes_gate


GATE = {"minimum_trades": 20, "minimum_stress_profit_factor": 1.15,
        "minimum_stress_net_return_pct": 0, "minimum_positive_year_ratio": .6,
        "maximum_stress_drawdown_pct": 20,
        "maximum_train_validation_expectancy_decay_pct": 50}


def scenarios(**changes):
    stress = {"trades": 30, "profit_factor": 1.3, "net_return_pct": 5,
              "positive_year_ratio": .8, "max_drawdown_pct": 10, "expectancy_bps": 15}
    stress.update(changes)
    return {"stress": stress}


def test_validation_gate_passes_complete_evidence():
    passed, decay = passes_gate(scenarios(), 20, GATE)
    assert passed and decay == 25


def test_validation_gate_rejects_insufficient_sample_or_decay():
    assert not passes_gate(scenarios(trades=11), 20, GATE)[0]
    assert not passes_gate(scenarios(expectancy_bps=5), 20, GATE)[0]
