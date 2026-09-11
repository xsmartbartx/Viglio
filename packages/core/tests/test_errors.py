from vigilo_core.errors import ErrorCode, StructuredError, error


def test_error_builds_structured_error_without_raising():
    err = error(ErrorCode.VALIDATION_ERROR, "bad payload", field="name")

    assert isinstance(err, StructuredError)
    assert err.code == ErrorCode.VALIDATION_ERROR
    assert err.message == "bad payload"
    assert err.context == {"field": "name"}


def test_structured_error_to_dict_is_json_shaped():
    err = StructuredError(ErrorCode.EGRESS_DENIED, "denied", host="10.0.0.1")

    assert err.to_dict() == {
        "code": "EGRESS_DENIED",
        "message": "denied",
        "context": {"host": "10.0.0.1"},
    }


def test_structured_error_is_raisable_as_exception():
    try:
        raise error(ErrorCode.NOT_FOUND, "missing")
    except StructuredError as exc:
        assert exc.code == ErrorCode.NOT_FOUND
    else:
        raise AssertionError("expected StructuredError to be raised")
