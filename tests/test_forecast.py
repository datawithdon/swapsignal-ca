from swapsignal.forecast import Day, find_streak


def days(*temps):
    return [Day(f"2026-11-{i + 1:02d}", t) for i, t in enumerate(temps)]


def test_finds_first_streak():
    s = find_streak(days(9, 6, 5, 4, 8, 1, 1, 1), 7, 3)
    assert (s.start, s.end, len(s.days), s.open_ended) == ("2026-11-02", "2026-11-04", 3, False)


def test_streak_too_short():
    assert find_streak(days(6, 6, 8, 6, 6, 9), 7, 3) is None


def test_exactly_threshold_is_not_cold():
    assert find_streak(days(7, 7, 7), 7, 3) is None
    assert find_streak(days(6.9, 6.9, 6.9), 7, 3) is not None


def test_open_ended_at_window_end():
    s = find_streak(days(10, 10, 5, 4, 3, 2), 7, 3)
    assert s.start == "2026-11-03" and s.open_ended and len(s.days) == 4


def test_none_breaks_streak():
    assert find_streak(days(5, None, 5, 5), 7, 3) is None


def test_starts_today():
    assert find_streak(days(1.4, 3.7, 6.9, 8.0), 7, 3).start == "2026-11-01"
