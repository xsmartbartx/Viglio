import hashlib

import pytest

from vigilo_core.redact import Fingerprint, redact


def test_redact_never_contains_the_original_value():
    secret = "sk_live_super_secret_value_12345"
    fp = redact(secret, kind="api_key")

    assert isinstance(fp, Fingerprint)
    assert secret not in str(fp)
    assert secret not in repr(fp)
    assert fp.prefix == "sk_l"
    assert fp.length == len(secret)
    assert fp.digest == hashlib.sha256(secret.encode("utf-8")).hexdigest()


def test_redact_default_kind_is_secret():
    fp = redact("abcdefgh")
    assert fp.kind == "secret"


def test_redact_same_value_produces_same_digest():
    a = redact("identical-value")
    b = redact("identical-value")
    assert a.digest == b.digest


def test_redact_rejects_empty_string():
    with pytest.raises(ValueError):
        redact("")
