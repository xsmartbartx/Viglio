"""generate_remediation(): Phase 4 returns each check's static
`remediation_template` verbatim — Phase 5 swaps this function's body for an
LLM call (redaction-gated, per `docs/build-roadmap.md`) without touching the
call site or the `RemediationPrompt` shape callers already depend on.
"""

from __future__ import annotations

from vigilo_core.models import CheckManifest, Finding
from vigilo_reporting.models import RemediationPrompt


def generate_remediation(
    finding: Finding, manifest: CheckManifest, stack_profile: str | None = None
) -> RemediationPrompt:
    return RemediationPrompt(
        check_id=finding.check_id, text=manifest.remediation_template, source="template"
    )
