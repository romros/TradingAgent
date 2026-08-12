from lab.sq_bridge.noncrypto_custom_block_build_v5 import FAMILIES, source


def test_six_families_generate_eleven_directional_blocks():
    assert len(FAMILIES) == 6
    assert sum(len(item["directions"]) for item in FAMILIES.values()) == 11


def test_generated_parameters_are_discrete_indices():
    for family, spec in FAMILIES.items():
        for direction in spec["directions"]:
            value = source(family, spec, direction)
            assert "Index" in value
            assert "minValue=0" in value
            assert "AlquimiaV5Signals." in value


def test_us500_has_no_short_block():
    assert FAMILIES["Us500D1VolatilityShockRebound"]["directions"] == ("Long",)
