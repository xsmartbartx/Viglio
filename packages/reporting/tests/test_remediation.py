from __future__ import annotations

import json

from vigilo_core.models import CheckManifest, Confidence, Finding, Severity, Tier, Verdict
from vigilo_reporting.remediation import generate_remediation, template_remediation


def _manifest() -> CheckManifest:
    return CheckManifest(
        check_id="VG-HDR-001",
        category="HDR",
        title="HSTS enforced",
        description="desc",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=8,
        tier_required=Tier.PASSIVE,
        references=["https://example.com/ref"],
        remediation_template="Add a Strict-Transport-Security header.",
        introduced_in="0.1",
    )


def _finding() -> Finding:
    return Finding(
        check_id="VG-HDR-001",
        verdict=Verdict.FAILED,
        severity=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        title="HSTS enforced",
        summary="No HSTS header present.",
        fingerprint="fp1",
    )


_VALID_RESPONSE = json.dumps(
    {
        "explanation": "The site never sends Strict-Transport-Security.",
        "impact": "Visitors can be downgraded to plain HTTP by a network attacker.",
        "remediation_steps": ["Add the header to every response."],
        "agent_prompt": "Add a Strict-Transport-Security header to all responses.",
        "estimated_effort": "trivial",
    }
)


def test_template_remediation_returns_the_manifests_static_template_verbatim():
    prompt = template_remediation(_finding(), _manifest())

    assert prompt.check_id == "VG-HDR-001"
    assert prompt.source == "template"
    assert prompt.remediation_steps == ["Add a Strict-Transport-Security header."]
    assert prompt.estimated_effort is None


async def test_generate_remediation_returns_llm_source_on_a_valid_response():
    async def fake_caller(prompt: str, system: str) -> str:
        return _VALID_RESPONSE

    prompt = await generate_remediation(_finding(), _manifest(), llm_caller=fake_caller)

    assert prompt.check_id == "VG-HDR-001"
    assert prompt.source == "llm"
    assert prompt.estimated_effort == "trivial"
    assert prompt.remediation_steps == ["Add the header to every response."]


async def test_generate_remediation_prompt_never_includes_target_origin():
    captured: dict = {}

    async def fake_caller(prompt: str, system: str) -> str:
        captured["prompt"] = prompt
        captured["system"] = system
        return _VALID_RESPONSE

    await generate_remediation(_finding(), _manifest(), llm_caller=fake_caller)

    assert "target_origin" not in captured["prompt"]
    assert "check_id: VG-HDR-001" in captured["prompt"]
    assert "untrusted" in captured["system"].lower()


async def test_generate_remediation_falls_back_to_template_on_malformed_json():
    async def fake_caller(prompt: str, system: str) -> str:
        return "not json at all"

    prompt = await generate_remediation(_finding(), _manifest(), llm_caller=fake_caller)

    assert prompt.source == "template"


async def test_generate_remediation_falls_back_to_template_on_missing_field():
    async def fake_caller(prompt: str, system: str) -> str:
        payload = json.loads(_VALID_RESPONSE)
        del payload["agent_prompt"]
        return json.dumps(payload)

    prompt = await generate_remediation(_finding(), _manifest(), llm_caller=fake_caller)

    assert prompt.source == "template"


async def test_generate_remediation_falls_back_to_template_on_invalid_estimated_effort():
    async def fake_caller(prompt: str, system: str) -> str:
        payload = json.loads(_VALID_RESPONSE)
        payload["estimated_effort"] = "not-a-real-value"
        return json.dumps(payload)

    prompt = await generate_remediation(_finding(), _manifest(), llm_caller=fake_caller)

    assert prompt.source == "template"


async def test_generate_remediation_falls_back_to_template_when_caller_raises():
    async def failing_caller(prompt: str, system: str) -> str:
        raise RuntimeError("simulated provider failure")

    prompt = await generate_remediation(_finding(), _manifest(), llm_caller=failing_caller)

    assert prompt.source == "template"


async def test_generate_remediation_falls_back_to_template_with_no_caller_and_no_config(
    monkeypatch,
):
    from vigilo_core.config import config

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config.cache_clear()

    prompt = await generate_remediation(_finding(), _manifest())

    assert prompt.source == "template"
    config.cache_clear()
