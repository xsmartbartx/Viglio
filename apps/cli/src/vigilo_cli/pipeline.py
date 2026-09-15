"""The checks+scoring half of a scan — pulled out of main.py so
test_determinism.py can run it twice against a fixture bundle without
touching argparse or the network at all.
"""

from __future__ import annotations

from vigilo_checks import REGISTRY, plan_registry, run_registry
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import Finding, Score, Tier
from vigilo_scoring import score as compute_score

REGISTRY_VERSION = "0.1"


def evaluate(bundle: EvidenceBundle, tier: Tier = Tier.PASSIVE) -> tuple[list[Finding], Score]:
    findings = run_registry(bundle, plan_registry(REGISTRY, tier))
    manifests_by_id = {check.manifest.check_id: check.manifest for check in REGISTRY}
    result = compute_score(findings, manifests_by_id, REGISTRY_VERSION)
    return findings, result
