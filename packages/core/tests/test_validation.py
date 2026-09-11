import pytest
from pydantic import BaseModel

from vigilo_core.errors import ErrorCode
from vigilo_core.validation import ValidationError, validate, validate_target_url


class _Widget(BaseModel):
    name: str
    count: int


def test_validate_returns_model_instance_on_success():
    widget = validate(_Widget, {"name": "thing", "count": 3})
    assert widget.name == "thing"
    assert widget.count == 3


def test_validate_raises_structured_validation_error_on_failure():
    with pytest.raises(ValidationError) as exc_info:
        validate(_Widget, {"name": "thing", "count": "not-a-number"})

    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


def test_validate_rejects_non_model_type():
    with pytest.raises(TypeError):
        validate(dict, {"a": 1})


@pytest.mark.parametrize(
    ("raw", "expected_origin"),
    [
        ("https://example.com", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("https://example.com/", "https://example.com"),
        ("https://example.com:443/some/path?q=1", "https://example.com"),
        ("http://example.com:80/", "http://example.com"),
        ("https://example.com:8443", "https://example.com:8443"),
        ("http://EXAMPLE.com", "http://example.com"),
    ],
)
def test_validate_target_url_accepts_and_canonicalizes(raw, expected_origin):
    assert validate_target_url(raw) == expected_origin


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://example.com",
        "http://user:pass@example.com",
        "https://example.com/#fragment",
        "https://1.2.3.4",
        "https://[::1]",
        "https://example.com:22",
        "not a url",
        "",
        "https://" + "a" * 300 + ".com",
    ],
)
def test_validate_target_url_rejects_invalid_targets(raw):
    with pytest.raises(ValidationError) as exc_info:
        validate_target_url(raw)
    assert exc_info.value.code == ErrorCode.TARGET_INVALID
