import json
from datetime import UTC, datetime

import pytest

import vigilo_cli.main as main_module
from vigilo_cli.main import build_parser, run
from vigilo_core.evidence import EvidenceBundle, HttpObservation


def test_build_parser_requires_a_url_for_scan():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["scan"])


def test_build_parser_accepts_scan_with_url():
    parser = build_parser()
    args = parser.parse_args(["scan", "https://example.com", "--json"])
    assert args.command == "scan"
    assert args.url == "https://example.com"
    assert args.json is True


def test_run_exits_cleanly_on_egress_denial(capsys):
    """A loopback target must be rejected by the egress guard before any
    network call happens — no mocking needed, this is real validation."""
    with pytest.raises(SystemExit) as exc_info:
        run(["scan", "http://127.0.0.1"])

    assert exc_info.value.code == 1
    assert "vigilo:" in capsys.readouterr().err


@pytest.fixture
def _fake_scan(monkeypatch):
    """Replaces the network-touching half of the pipeline (`run_probes`)
    with a canned bundle, so this test exercises argparse -> asyncio.run ->
    pipeline.evaluate -> printing, with zero real I/O."""

    async def fake_run_probes(url: str):
        return EvidenceBundle(
            bundle_id="fixture",
            target_origin=url,
            captured_at=datetime.now(UTC),
            http=HttpObservation(
                url=url,
                status_code=200,
                headers={"strict-transport-security": "max-age=31536000; includeSubDomains"},
                content_type="text/html",
            ),
        )

    async def fake_run_scan(url: str):
        bundle = await fake_run_probes(url)
        findings, result = main_module.evaluate(bundle)
        return bundle, findings, result

    monkeypatch.setattr(main_module, "_run_scan", fake_run_scan)


def test_run_prints_json_for_a_scan(_fake_scan, capsys):
    with pytest.raises(SystemExit) as exc_info:
        run(["scan", "https://safe.test", "--json"])

    assert exc_info.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["target_origin"] == "https://safe.test"
    assert "score" in payload
    assert len(payload["findings"]) == 20


def test_run_prints_human_summary_by_default(_fake_scan, capsys):
    with pytest.raises(SystemExit) as exc_info:
        run(["scan", "https://safe.test"])

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "Vigilo scan: https://safe.test" in out
    assert "Score:" in out


def test_run_saves_evidence_when_requested(_fake_scan, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        run(["scan", "https://safe.test", "--save-evidence", str(tmp_path)])

    assert exc_info.value.code == 0
    saved = list(tmp_path.rglob("*.json"))
    assert len(saved) == 1
