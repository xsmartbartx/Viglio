"""The concrete version of docs/architecture.md §6: "a check module importing
`httpx`, `socket` or `os` fails the build." Parses the AST of every module
under `src/vigilo_checks/` — no execution, no import — and asserts every
import resolves to the standard library or `vigilo_core`. Checks may not
perform I/O, so this is the boundary that actually enforces it.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "vigilo_checks"
_ALLOWED_PACKAGE_PREFIXES = ("vigilo_core", "vigilo_checks")

if sys.version_info >= (3, 10):
    _STDLIB_NAMES = sys.stdlib_module_names
else:  # pragma: no cover - project requires >=3.11
    raise RuntimeError("test requires Python 3.10+ for sys.stdlib_module_names")


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
                continue  # relative import within vigilo_checks itself
            if node.module:
                names.add(_top_level_module(node.module))
    return names


def _check_module_paths() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def test_check_modules_import_only_stdlib_or_core():
    violations: dict[str, set[str]] = {}

    for path in _check_module_paths():
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
        "packages/checks may depend on the standard library and vigilo_core "
        f"only (docs/modules.md §4); found disallowed imports: {violations}"
    )


def test_there_are_check_modules_to_scan():
    """Guards against this test silently passing over an empty directory."""
    assert len(_check_module_paths()) >= 3
