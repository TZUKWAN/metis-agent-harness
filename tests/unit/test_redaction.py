from metis.security.redaction import redact_secrets


def test_redaction_replaces_credentials():
    text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz token=secretvalue123 password: hunter2222"

    redacted = redact_secrets(text)

    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "secretvalue123" not in redacted
    assert "hunter2222" not in redacted
    assert redacted.count("[REDACTED]") >= 3
