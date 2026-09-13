"""Vigilo checks: pure functions that convert evidence into findings
(docs/modules.md §4). Depends on `vigilo_core` only — enforced by
tests/test_import_boundary.py, not just documented.
"""

from vigilo_checks import cli, cmp, dat, dep, exp, hdr, leg, ses, tls
from vigilo_checks.findings import run_registry, to_findings
from vigilo_checks.registry import Check, CheckResult, get_header, requires

REGISTRY: list[Check] = [
    *hdr.CHECKS,
    *tls.CHECKS,
    *ses.CHECKS,
    *leg.CHECKS,
    *dep.CHECKS,
    *cmp.CHECKS,
    *cli.CHECKS,
    *exp.CHECKS,
    *dat.CHECKS,
]

__all__ = [
    "Check",
    "CheckResult",
    "get_header",
    "requires",
    "run_registry",
    "to_findings",
    "REGISTRY",
]
