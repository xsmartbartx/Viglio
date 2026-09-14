"""render_badge(): a pure SVG string, colored via `config().brand.theme`.
No API route, no caching, no embed page this phase — `docs/build-roadmap.md`
places the embeddable badge at Phase 8, where `brand.config.json`'s already-
reserved `namespaces.badgePath` finally gets consumed. Built now only
because the function itself is small and self-contained.
"""

from __future__ import annotations

from datetime import datetime

from vigilo_core.config import config
from vigilo_core.models import Score

_GRADE_COLOR_FIELD = {
    "A": "colorPass",
    "B": "colorPass",
    "C": "colorMedium",
    "D": "colorHigh",
    "F": "colorCritical",
}


def _color_for_grade(grade: str) -> str:
    theme = config().brand.theme
    field = _GRADE_COLOR_FIELD.get(grade, "colorCritical")
    if theme is None:
        return "#999999"
    return getattr(theme, field)


def render_badge(score: Score, generated_at: datetime) -> str:
    color = _color_for_grade(score.grade)
    date_label = generated_at.date().isoformat()
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="180" height="20" role="img" '
        f'aria-label="Vigilo score: {score.grade}">'
        '<rect width="180" height="20" rx="3" fill="#555"/>'
        f'<rect x="80" width="100" height="20" rx="3" fill="{color}"/>'
        '<g fill="#fff" font-family="Verdana,sans-serif" font-size="11">'
        '<text x="8" y="14">vigilo score</text>'
        f'<text x="88" y="14">{score.grade} ({score.value:.0f}) · {date_label}</text>'
        "</g>"
        "</svg>"
    )
