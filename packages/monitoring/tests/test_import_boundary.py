"""The concrete enforcement of `packages/monitoring`'s documented boundary
(docs/modules.md §9): parses the AST of every module under
`src/vigilo_monitoring/`, no execution, and asserts every import resolves
to the standard library, `pydantic`/`sqlalchemy` (this module owns real
persistence, unlike `billing`/`checks` — it uses the same Pydantic-model +
SQLAlchemy-ORM shape `identity`/`project` already establish, not `billing`'s
stricter dataclass-only convention), `vigilo_core`, `vigilo_persistence`,
or `vigilo_orchestrator`. `vigilo_scoring` was in the module's originally
sketched dependency list but nothing here actually needs it — score-drop
detection is a fixed threshold, not a scoring-module concept — so it was
dropped, matching `packages/checks/tests/test_import_boundary.py`'s exact
enforcement pattern (adapted for this module's actual, larger footprint).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "vigilo_monitoring"
_ALLOWED_PACKAGE_PREFIXES = (
    "vigilo_core",
    "vigilo_persistence",
    "vigilo_orchestrator",
    "vigilo_monitoring",
)
_ALLOWED_THIRD_PARTY = {"pydantic", "sqlalchemy"}
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
                continue  # relative import within vigilo_monitoring itself
            if node.module:
                names.add(_top_level_module(node.module))
    return names


def _monitoring_module_paths() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def test_monitoring_modules_import_only_stdlib_core_persistence_or_orchestrator():
    violations: dict[str, set[str]] = {}

    for path in _monitoring_module_paths():
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
        "packages/monitoring may depend on the standard library, pydantic, "
        "sqlalchemy, vigilo_core, vigilo_persistence and vigilo_orchestrator "
        f"only (docs/modules.md §9); found disallowed imports: {violations}"
    )


def test_there_are_monitoring_modules_to_scan():
    """Guards against this test silently passing over an empty directory."""
    assert len(_monitoring_module_paths()) >= 3
