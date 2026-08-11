from lab.sq_bridge.crypto_h4_sq_proposal_replay_v4 import gross_gate


def test_gross_gate_rejects_before_costs_when_pf_cannot_pass():
    decision, reasons = gross_gate({"closed_trades": 100, "profit_factor": 1.19,
                                    "net_pnl_usdc": 10,
                                    "positive_calendar_years_ratio": .8})
    assert decision == "REJECT_SQ_PROPOSAL_CANONICAL_GROSS"
    assert reasons == ["GROSS_PROFIT_FACTOR_BELOW_1_2"]
