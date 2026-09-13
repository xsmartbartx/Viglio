#!/usr/bin/env python3
"""Generates docs/check-catalog.md from vigilo_checks.REGISTRY.

Run after any change to a check manifest:

    uv run python scripts/generate_check_catalog.py

Per docs/build-roadmap.md Phase 2: "docs/check-catalog.md generated from the
descriptors, not hand-maintained." This script has no CI enforcement yet
(a drift check — regenerate and diff — is a reasonable follow-up, not
required for Phase 2); regeneration is a manual step for now.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from vigilo_checks import REGISTRY

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_PATH = _REPO_ROOT / "docs" / "check-catalog.md"

_CATEGORY_NAMES = {
    "HDR": "Response headers",
    "TLS": "Transport & TLS",
    "SES": "Cookies & sessions",
    "CLI": "Client-side exposure",
    "EXP": "Surface exposure",
    "DAT": "Data platform posture",
    "DEP": "Dependencies",
    "CMP": "Compliance",
    "LEG": "Legal documents",
}


def _table_for_category(category: str, checks) -> str:
    lines = [
        f"## {category} — {_CATEGORY_NAMES.get(category, category)}",
        "",
        "| ID | Title | Severity | Confidence | Tier | Weight | Reference |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for check in sorted(checks, key=lambda c: c.manifest.check_id):
        m = check.manifest
        ref = m.references[0] if m.references else ""
        ref_cell = f"[link]({ref})" if ref else ""
        lines.append(
            f"| `{m.check_id}` | {m.title} | {m.severity_default.value} "
            f"| {m.confidence.value} | {m.tier_required.value} | {m.weight:g} | {ref_cell} |"
        )
    lines.append("")
    return "\n".join(lines)


def generate() -> str:
    by_category: dict[str, list] = defaultdict(list)
    for check in REGISTRY:
        by_category[check.manifest.category].append(check)

    header = [
        "# Check catalog",
        "",
        "**Generated from `vigilo_checks.REGISTRY` — do not hand-edit.** "
        "Regenerate with `uv run python scripts/generate_check_catalog.py` "
        "after any manifest change (docs/build-roadmap.md Phase 2 exit criterion).",
        "",
        f"**{len(REGISTRY)} checks** across {len(by_category)} categories.",
        "",
    ]

    sections = [_table_for_category(cat, checks) for cat, checks in sorted(by_category.items())]
    return "\n".join(header) + "\n" + "\n".join(sections)


def main() -> None:
    content = generate()
    _OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {_OUTPUT_PATH.relative_to(_REPO_ROOT)} ({len(REGISTRY)} checks)")


if __name__ == "__main__":
    main()
