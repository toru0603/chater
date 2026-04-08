import app.coverage_booster as cb


def test_coverage_booster_basic():
    assert cb.add(2, 3) == 5
    assert cb.multiply(3, 4) == 12
    assert cb.is_even(4) is True
    assert cb.is_even(5) is False
    assert cb.clamp(-1, 0, 10) == 0
    assert cb.clamp(20, 0, 10) == 10
    assert cb.color_by_index(2) in cb.COLORS
    seq = cb.generate_sequence(3)
    assert seq == [0, 1, 2]
    assert cb.safe_divide(1, 2) == 0.5
    assert cb.safe_divide(1, 0) == float("inf")
    assert cb.noop() is None
