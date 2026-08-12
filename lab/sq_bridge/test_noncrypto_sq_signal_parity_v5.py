from lab.sq_bridge.noncrypto_sq_signal_parity_v5 import oracle_rows


def test_oracle_is_deterministic_and_has_six_signal_columns():
    rows_a, expected_a = oracle_rows()
    rows_b, expected_b = oracle_rows()
    assert rows_a == rows_b
    assert expected_a == expected_b
    assert len(rows_a) == 960
    assert all(len(row) == 6 for row in expected_a)


def test_oracle_exercises_wait_and_at_least_one_entry_per_signal():
    _, expected = oracle_rows()
    for index in range(6):
        values = {row[index] for row in expected[120:]}
        assert 0 in values
        assert values - {0}, f"signal {index} has no entry coverage"
