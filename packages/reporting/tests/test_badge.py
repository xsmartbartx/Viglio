from __future__ import annotations

from datetime import UTC, datetime

from vigilo_core.models import Score
from vigilo_reporting.badge import render_badge


def _score(grade: str, value: float) -> Score:
    return Score(value=value, grade=grade, registry_version="0.1")


def test_render_badge_returns_an_svg_string_containing_the_grade():
    svg = render_badge(_score("A", 96.0), datetime(2026, 9, 14, tzinfo=UTC))

    assert svg.startswith("<svg")
    assert "A (96)" in svg
    assert "2026-09-14" in svg


def test_a_failing_grade_still_renders():
    svg = render_badge(_score("F", 12.0), datetime(2026, 9, 14, tzinfo=UTC))

    assert "F (12)" in svg
