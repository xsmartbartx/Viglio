"""The concrete enforcement of docs/architecture.md §3: "the control plane
never makes an outbound request to a target, ever." `vigilo_probes` is the
only module permitted to make outbound requests to a target
(docs/modules.md §3) — so no module under `apps/api/src` may import it,
directly or via `vigilo_orchestrator.jobs` (the ARQ task bodies, which do
import it, live in `apps/scanner`'s worker, never here).

Same AST-based, no-execution approach as
`packages/checks/tests/test_import_boundary.py`, inverted into a denylist
since `apps/api` legitimately depends on many packages — the constraint is
specifically about this one module, not about depending on few.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "vigilo_api"
_DENIED_PREFIXES = ("vigilo_probes", "vigilo_orchestrator.jobs", "vigilo_scanner")


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                names.add(node.module)
    return names


def _api_module_paths() -> list[Path]:
    return sorted(_SRC_ROOT.rglob("*.py"))


def test_api_never_imports_the_probing_layer_or_the_scan_worker():
    violations: dict[str, set[str]] = {}

    for path in _api_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_names(tree)
        disallowed = {
            name for name in imported if any(name.startswith(prefix) for prefix in _DENIED_PREFIXES)
        }
        if disallowed:
            violations[str(path.relative_to(_SRC_ROOT))] = disallowed

    assert not violations, (
        "apps/api must never import the probing layer or the scan worker "
        f"(docs/architecture.md §3); found: {violations}"
    )


def test_there_are_api_modules_to_scan():
    assert len(_api_module_paths()) >= 3
