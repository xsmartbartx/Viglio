"""The concrete enforcement of `packages/billing`'s documented boundary
(docs/modules.md §11: "Dependencies: core.") — parses the AST of every
module under `src/vigilo_billing/`, no execution, and asserts every import
resolves to the standard library or `vigilo_core`. This is what stops the
architecture from being quietly violated later (e.g. "just add one DB
query to consume()") — matching `packages/checks/tests/test_import_boundary.py`'s
exact pattern.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "vigilo_billing"
_ALLOWED_PACKAGE_PREFIXES = ("vigilo_core", "vigilo_billing")
_STDLIB_NAMES = sys.stdlib_module_names


def _top_level_module(name: str) -> str:
    return name.split(".", 1)[0]


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(_top_level_module(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import within vigilo_billing itself
            if node.module:
                names.add(_top_level_module(node.module))
    return names


def _billing_module_paths() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def test_billing_modules_import_only_stdlib_or_core():
    violations: dict[str, set[str]] = {}

    for path in _billing_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_names(tree)
        disallowed = {
            name
            for name in imported
            if name not in _STDLIB_NAMES
            and not name.startswith(_ALLOWED_PACKAGE_PREFIXES)
            and name != "__future__"
        }
        if disallowed:
            violations[str(path.relative_to(_SRC_ROOT))] = disallowed

    assert not violations, (
        "packages/billing may depend on the standard library and vigilo_core "
        f"only (docs/modules.md §11); found disallowed imports: {violations}"
    )


def test_there_are_billing_modules_to_scan():
    """Guards against this test silently passing over an empty directory."""
    assert len(_billing_module_paths()) >= 3
