"""`vigilo scan <url>` — the Phase 1 CLI entry point.

Ties `vigilo_probes.run_probes` -> `vigilo_cli.pipeline.evaluate` (checks +
scoring) together and prints a human-readable summary, `--json`, or
`--sarif` (for GitHub Code Scanning — see `.github/actions/scan`, the
GitHub Action this CLI is the standalone engine for). `--fail-on` makes
the process exit non-zero when a failed finding meets or exceeds a given
severity, for CI gating — this is the only flag that changes the exit
code; the scan itself and its output are identical either way, so
`--sarif --fail-on high` produces both the CI artifact and the pass/fail
decision from a single live scan, never two.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from vigilo_checks import REGISTRY
from vigilo_cli.pipeline import evaluate
from vigilo_core.errors import StructuredError
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Finding, Score, Verdict
from vigilo_probes import run_probes
from vigilo_probes.store import LocalFileEvidenceStore
from vigilo_reporting import build_sarif_report

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _print_human(bundle: EvidenceBundle, findings: list[Finding], result: Score) -> None:
    print(f"Vigilo scan: {bundle.target_origin}")
    print(f"Score: {result.value:.1f}  Grade: {result.grade}  (registry {result.registry_version})")
    print()

    failed = [f for f in findings if f.verdict == Verdict.FAILED]
    if not failed:
        print("No failed checks.")
    else:
        print(f"{len(failed)} finding(s):")
        for f in sorted(failed, key=lambda x: _SEVERITY_ORDER.get(x.severity.value, 99)):
            print(f"  [{f.severity.value.upper():>8}] {f.check_id}  {f.title}")
            print(f"      {f.summary}")

    inconclusive = [f for f in findings if f.verdict == Verdict.INCONCLUSIVE]
    if inconclusive:
        print()
        print(f"{len(inconclusive)} check(s) inconclusive (insufficient evidence):")
        for f in inconclusive:
            print(f"  {f.check_id}  {f.summary}")


def _print_json(bundle: EvidenceBundle, findings: list[Finding], result: Score) -> None:
    payload = {
        "target_origin": bundle.target_origin,
        "bundle_id": bundle.bundle_id,
        "score": json.loads(result.model_dump_json()),
        "findings": [json.loads(f.model_dump_json()) for f in findings],
    }
    print(json.dumps(payload, indent=2))


def _print_sarif(
    bundle: EvidenceBundle, findings: list[Finding], manifests_by_check_id: dict[str, CheckManifest]
) -> None:
    report = build_sarif_report(bundle.target_origin, findings, manifests_by_check_id)
    print(json.dumps(report, indent=2))


async def _run_scan(url: str) -> tuple[EvidenceBundle, list[Finding], Score]:
    bundle = await run_probes(url)
    findings, result = evaluate(bundle)
    return bundle, findings, result


def _breaches_threshold(findings: list[Finding], fail_on: str) -> bool:
    threshold = _SEVERITY_ORDER[fail_on]
    return any(
        f.verdict == Verdict.FAILED and _SEVERITY_ORDER.get(f.severity.value, 99) <= threshold
        for f in findings
    )


def _cmd_scan(args: argparse.Namespace) -> int:
    try:
        bundle, findings, result = asyncio.run(_run_scan(args.url))
    except StructuredError as exc:
        print(f"vigilo: {exc.code.value}: {exc.message}", file=sys.stderr)
        return 1

    if args.save_evidence:
        store = LocalFileEvidenceStore(args.save_evidence)
        path = store.save(bundle)
        print(f"Evidence saved to {path}", file=sys.stderr)

    if args.sarif:
        manifests_by_check_id = {c.manifest.check_id: c.manifest for c in REGISTRY}
        _print_sarif(bundle, findings, manifests_by_check_id)
    elif args.json:
        _print_json(bundle, findings, result)
    else:
        _print_human(bundle, findings, result)

    if args.fail_on and _breaches_threshold(findings, args.fail_on):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vigilo", description="Security scanning for AI-generated web apps."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a target URL")
    scan_parser.add_argument("url", help="Target URL, e.g. https://example.com")
    output_format = scan_parser.add_mutually_exclusive_group()
    output_format.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON instead of a summary"
    )
    output_format.add_argument(
        "--sarif",
        action="store_true",
        help="Print a SARIF 2.1.0 report instead of a summary, for GitHub Code Scanning",
    )
    scan_parser.add_argument(
        "--fail-on",
        choices=list(_SEVERITY_ORDER),
        default=None,
        help="Exit 1 if any failed finding is at or above this severity (for CI gating)",
    )
    scan_parser.add_argument(
        "--save-evidence", metavar="DIR", help="Save the sealed evidence bundle under DIR"
    )
    scan_parser.set_defaults(func=_cmd_scan)

    return parser


def run(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    run()
