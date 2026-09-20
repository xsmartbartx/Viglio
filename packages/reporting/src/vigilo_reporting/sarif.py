"""build_sarif_report(): a SARIF 2.1.0 rendering of a scan's findings, for
GitHub Code Scanning (`apps/cli --sarif`, `GET /public/v1/scans/{id}/report.sarif`).
Pure function, same convention as `build_report()` (`builder.py`) — no I/O,
no self-fetching, every input already fetched by the caller.

**A genuine adaptation, not a perfect fit.** GitHub Code Scanning's SARIF
ingestion expects `results[].locations[].physicalLocation.artifactLocation.uri`
to be a repo-relative source file with a line/column region — Vigilo's
findings are about a live deployed URL, which has neither. There is no
documented convention for this (checked GitHub's own SARIF docs and the
OWASP ZAP GitHub Action, neither addresses DAST-style findings). This
module uses the scanned origin as the location's `uri` — honest about
there being no file, rather than pointing at an unrelated real one — with
an inert `region`. GitHub's schema validation should accept this and list
findings in the Security tab even without a meaningful inline code
annotation; that assumption should be confirmed against a real GitHub
Code Scanning upload on first real-world use (docs/build-roadmap.md's
SARIF entry).

Only `FAILED` and `INCONCLUSIVE` findings become SARIF results —
`PASSED`/`NOT_APPLICABLE` are never emitted, matching SARIF's own
convention of reporting actionable findings, not every rule that ran
clean. `INCONCLUSIVE` is still surfaced (as a `note`), never hidden — the
same "never silently fold into passed" rule this product applies to its
own web report.
"""

from __future__ import annotations

from vigilo_core.models import CheckManifest, Finding, Severity, Verdict

_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
_TOOL_NAME = "Vigilo"
_TOOL_INFO_URI = "https://vigilo.io"

# GitHub's documented numeric band for properties.security-severity (0.0-10.0).
_SECURITY_SEVERITY = {
    Severity.CRITICAL: 9.0,
    Severity.HIGH: 7.0,
    Severity.MEDIUM: 5.0,
    Severity.LOW: 3.0,
    Severity.INFO: 1.0,
}

# error/warning/note — GitHub's three supported result levels.
_FAILED_LEVEL = {
    Severity.CRITICAL: "error",
    Severity.HIGH: "error",
    Severity.MEDIUM: "warning",
    Severity.LOW: "note",
    Severity.INFO: "note",
}


def _rule(manifest: CheckManifest) -> dict:
    tags = ["security"]
    if manifest.cwe_id:
        tags.append(f"external/cwe/{manifest.cwe_id.lower()}")

    rule: dict = {
        "id": manifest.check_id,
        "shortDescription": {"text": manifest.title},
        "fullDescription": {"text": manifest.description},
        "help": {"text": manifest.remediation_template},
        "defaultConfiguration": {"level": _FAILED_LEVEL[manifest.severity_default]},
        "properties": {
            "security-severity": str(_SECURITY_SEVERITY[manifest.severity_default]),
            "tags": tags,
        },
    }
    if manifest.references:
        rule["helpUri"] = manifest.references[0]
    return rule


def _result(finding: Finding, manifest: CheckManifest, target_origin: str) -> dict:
    level = "note" if finding.verdict == Verdict.INCONCLUSIVE else _FAILED_LEVEL[finding.severity]
    message = finding.summary
    if finding.verdict == Verdict.INCONCLUSIVE:
        message = f"Could not be checked: {finding.summary}"

    return {
        "ruleId": finding.check_id,
        "level": level,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": target_origin},
                    "region": {
                        "startLine": 1,
                        "startColumn": 1,
                        "endLine": 1,
                        "endColumn": 1,
                    },
                }
            }
        ],
        "partialFingerprints": {"primaryLocationLineHash": finding.fingerprint},
    }


def build_sarif_report(
    target_origin: str,
    findings: list[Finding],
    manifests_by_check_id: dict[str, CheckManifest],
) -> dict:
    reportable = [f for f in findings if f.verdict in (Verdict.FAILED, Verdict.INCONCLUSIVE)]
    manifests_used = {
        manifests_by_check_id[finding.check_id].check_id: manifests_by_check_id[finding.check_id]
        for finding in reportable
    }

    return {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _TOOL_NAME,
                        "informationUri": _TOOL_INFO_URI,
                        "rules": [
                            _rule(manifest)
                            for _, manifest in sorted(manifests_used.items())
                        ],
                    }
                },
                "results": [
                    _result(finding, manifests_by_check_id[finding.check_id], target_origin)
                    for finding in reportable
                ],
            }
        ],
    }
