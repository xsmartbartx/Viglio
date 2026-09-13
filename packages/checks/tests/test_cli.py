from datetime import UTC, datetime

from vigilo_checks import cli
from vigilo_core.evidence import BundleObservation, EvidenceBundle, FetchedScript
from vigilo_core.models import Verdict


def _bundle(bundle_obs: BundleObservation | None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test", target_origin="https://example.com", captured_at=datetime.now(UTC), bundle=bundle_obs
    )


def _scripts(*excerpts: str) -> BundleObservation:
    return BundleObservation(
        fetched_scripts=[FetchedScript(url=f"https://example.com/s{i}.js", excerpt=e) for i, e in enumerate(excerpts)]
    )


def _v(check, bundle_obs):
    return check.evaluate(_bundle(bundle_obs)).verdict


def test_all_cli_checks_are_inconclusive_without_bundle_evidence():
    for check in cli.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_no_aws_key():
    clean = _scripts("const x = 1;")
    leaking = _scripts('const key = "AKIAABCDEFGHIJKLMNOP";')

    assert _v(cli.CHECK_NO_AWS_KEY, clean) == Verdict.PASSED
    result = cli.CHECK_NO_AWS_KEY.evaluate(_bundle(leaking))
    assert result.verdict == Verdict.FAILED
    assert "AKIAABCDEFGHIJKLMNOP" not in result.matched_indicator


def test_no_stripe_secret_key():
    clean = _scripts("const pk = 'pk_live_abc';")
    leaking = _scripts("const sk = 'sk_live_abcdefghij1234567890';")

    assert _v(cli.CHECK_NO_STRIPE_SECRET_KEY, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_STRIPE_SECRET_KEY, leaking) == Verdict.FAILED


def test_no_slack_token():
    clean = _scripts("const x = 1;")
    leaking = _scripts("const t = 'xoxb-1234567890-abcdefghij';")

    assert _v(cli.CHECK_NO_SLACK_TOKEN, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_SLACK_TOKEN, leaking) == Verdict.FAILED


def test_no_github_gitlab_token():
    clean = _scripts("const x = 1;")
    leaking = _scripts("const t = 'ghp_" + "a" * 36 + "';")

    assert _v(cli.CHECK_NO_GITHUB_GITLAB_TOKEN, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_GITHUB_GITLAB_TOKEN, leaking) == Verdict.FAILED


def test_no_private_key_block():
    clean = _scripts("const x = 1;")
    leaking = _scripts("const k = `-----BEGIN RSA PRIVATE KEY-----\\nMIIEow...`;")

    assert _v(cli.CHECK_NO_PRIVATE_KEY_BLOCK, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_PRIVATE_KEY_BLOCK, leaking) == Verdict.FAILED


def test_no_generic_secret():
    clean = _scripts("const publicId = 'app-123';")
    leaking = _scripts('const API_SECRET = "abcdefghij1234567890ABCDEFGHIJ";')

    assert _v(cli.CHECK_NO_GENERIC_SECRET, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_GENERIC_SECRET, leaking) == Verdict.FAILED


def test_no_source_map_comment():
    clean = _scripts("console.log('done');")
    leaking = _scripts("console.log('done');\n//# sourceMappingURL=app.js.map")

    assert _v(cli.CHECK_NO_SOURCE_MAP_COMMENT, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_SOURCE_MAP_COMMENT, leaking) == Verdict.FAILED


def test_no_dev_build_marker():
    clean = _scripts("function a(){}")
    leaking = _scripts("if (process.env.NODE_ENV !== 'production') { console.warn('dev'); }")

    assert _v(cli.CHECK_NO_DEV_BUILD_MARKER, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_DEV_BUILD_MARKER, leaking) == Verdict.FAILED


def test_bounded_console_calls():
    few = _scripts("console.log('a'); console.log('b');")
    many = _scripts("".join("console.log('x');" for _ in range(15)))

    assert _v(cli.CHECK_BOUNDED_CONSOLE_CALLS, few) == Verdict.PASSED
    assert _v(cli.CHECK_BOUNDED_CONSOLE_CALLS, many) == Verdict.FAILED


def test_no_hardcoded_internal_hostname():
    clean = _scripts("fetch('https://api.example.com/v1');")
    leaking = _scripts("fetch('http://192.168.1.5:8000/debug');")

    assert _v(cli.CHECK_NO_HARDCODED_INTERNAL_HOSTNAME, clean) == Verdict.PASSED
    assert _v(cli.CHECK_NO_HARDCODED_INTERNAL_HOSTNAME, leaking) == Verdict.FAILED
