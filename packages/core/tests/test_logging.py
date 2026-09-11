import json

from vigilo_core.logging import LogEvent, Severity, log


def test_log_emits_json_line_to_stdout(capsys):
    log(LogEvent(event="scan.requested", severity=Severity.INFO, module="project", context={"target_id": "t_1"}))

    out = capsys.readouterr().out.strip()
    record = json.loads(out)

    assert record["event"] == "scan.requested"
    assert record["severity"] == "INFO"
    assert record["module"] == "project"
    assert record["context"] == {"target_id": "t_1"}
    assert "timestamp" in record


def test_log_redacts_well_known_sensitive_keys(capsys):
    log(
        LogEvent(
            event="auth.attempt",
            severity=Severity.SECURITY,
            module="identity",
            context={"password": "hunter2", "user_id": "u_1"},
        )
    )

    record = json.loads(capsys.readouterr().out.strip())
    assert record["context"]["password"] == "<REDACTED>"
    assert record["context"]["user_id"] == "u_1"


def test_log_redacts_nested_sensitive_keys(capsys):
    log(
        LogEvent(
            event="webhook.received",
            severity=Severity.INFO,
            module="billing",
            context={"headers": {"Authorization": "irrelevant"}},
        )
    )

    record = json.loads(capsys.readouterr().out.strip())
    assert record["context"]["headers"]["Authorization"] == "<REDACTED>"
