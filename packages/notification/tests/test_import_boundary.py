"""The concrete enforcement of `packages/notification`'s documented
boundary (docs/modules.md §10: "Dependencies: core, integrations."):
parses the AST of every module under `src/vigilo_notification/`, no
execution, and asserts every import resolves to the standard library,
`httpx` (integrations' own transport-DI type), `vigilo_core`, or
`vigilo_integrations` — never `vigilo_monitoring`, matching the "renders
and delivers what monitoring produced, no decision logic" boundary.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "vigilo_notification"
_ALLOWED_PACKAGE_PREFIXES = ("vigilo_core", "vigilo_integrations", "vigilo_notification")
_ALLOWED_THIRD_PARTY = {"httpx"}
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
                continue  # relative import within vigilo_notification itself
            if node.module:
                names.add(_top_level_module(node.module))
    return names


def _notification_module_paths() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def test_notification_modules_import_only_stdlib_httpx_core_or_integrations():
    violations: dict[str, set[str]] = {}

    for path in _notification_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_names(tree)
        disallowed = {
            name
            for name in imported
            if name not in _STDLIB_NAMES
            and name not in _ALLOWED_THIRD_PARTY
            and not name.startswith(_ALLOWED_PACKAGE_PREFIXES)
            and name != "__future__"
        }
        if disallowed:
            violations[str(path.relative_to(_SRC_ROOT))] = disallowed

    assert not violations, (
        "packages/notification may depend on the standard library, httpx, "
        "vigilo_core and vigilo_integrations only (docs/modules.md §10); "
        f"found disallowed imports: {violations}"
    )


def test_there_are_notification_modules_to_scan():
    """Guards against this test silently passing over an empty directory."""
    assert len(_notification_module_paths()) >= 3
