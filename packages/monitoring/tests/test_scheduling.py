from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vigilo_monitoring.scheduling import compute_next_run_at

_NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


def test_next_run_at_is_roughly_now_plus_cadence():
    next_run = compute_next_run_at(24, None, None, _NOW, jitter_minutes=15)

    delta = next_run - _NOW
    assert 23 * 3600 - 15 * 60 <= delta.total_seconds() <= 24 * 3600 + 15 * 60


def test_jitter_varies_across_calls():
    results = {compute_next_run_at(24, None, None, _NOW) for _ in range(20)}
    assert len(results) > 1


def test_a_candidate_inside_quiet_hours_is_pushed_to_quiet_end_same_day():
    # cadence lands at 12:00 + 22h = 10:00 the next day, inside [7, 12).
    next_run = compute_next_run_at(22, 7, 12, _NOW, jitter_minutes=0)

    assert next_run.hour == 12
    assert next_run.date() == (_NOW + timedelta(hours=22)).date()


def test_a_candidate_in_a_wrapped_quiet_window_late_at_night_pushes_to_next_day():
    # cadence lands at 12:00 + 34h = 22:00 two days later, inside a
    # wrapped [22, 7) quiet window's "late night" half.
    next_run = compute_next_run_at(34, 22, 7, _NOW, jitter_minutes=0)

    assert next_run.hour == 7
    landing_day = (_NOW + timedelta(hours=34)).date()
    assert next_run.date() == landing_day + timedelta(days=1)


def test_a_candidate_in_a_wrapped_quiet_window_early_morning_pushes_same_day():
    # cadence lands at 12:00 + 41h = 05:00 two days later, inside a
    # wrapped [22, 7) quiet window's "early morning" half.
    next_run = compute_next_run_at(41, 22, 7, _NOW, jitter_minutes=0)

    assert next_run.hour == 7
    landing_day = (_NOW + timedelta(hours=41)).date()
    assert next_run.date() == landing_day


def test_a_candidate_outside_quiet_hours_is_unaffected():
    # cadence lands at 12:00 + 2h = 14:00, outside [22, 7).
    next_run = compute_next_run_at(2, 22, 7, _NOW, jitter_minutes=0)

    assert next_run.hour == 14


def test_equal_quiet_start_and_end_means_no_quiet_hours():
    next_run = compute_next_run_at(24, 9, 9, _NOW, jitter_minutes=0)

    assert next_run.hour == _NOW.hour
