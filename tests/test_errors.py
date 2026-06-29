import pytest
from autotest_ide.core.errors import (
    PocoError,
    PocoConnectionError,
    PocoTimeoutError,
    PocoProtocolError,
    PocoRemoteError,
    PocoNodeNotFoundError,
)


def test_all_errors_subclass_poco_error():
    for exc in [
        PocoConnectionError("x"),
        PocoTimeoutError("x"),
        PocoProtocolError("x"),
        PocoRemoteError(1, "x"),
        PocoNodeNotFoundError("x"),
    ]:
        assert isinstance(exc, PocoError)


def test_poco_remote_error_carries_code_message_data():
    err = PocoRemoteError(code=-32601, message="method not found", data={"method": "foo"})
    assert err.code == -32601
    assert err.message == "method not found"
    assert err.data == {"method": "foo"}
    assert "[-32601]" in str(err)
    assert "method not found" in str(err)


def test_poco_remote_error_data_defaults_none():
    err = PocoRemoteError(code=1, message="boom")
    assert err.data is None
