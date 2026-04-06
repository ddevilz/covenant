from __future__ import annotations

import pytest

from covenant.errors import CovenantViolationError, _ALL_CODES


def test_valid_code_roundtrip() -> None:
    err = CovenantViolationError(code="UNDECLARED_TOOL", detail={"tool": "bash"})
    assert err.code == "UNDECLARED_TOOL"
    assert err.detail == {"tool": "bash"}
    assert err.timestamp is not None


def test_all_codes_accepted() -> None:
    for code in _ALL_CODES:
        err = CovenantViolationError(code=code, detail={})
        assert err.code == code


def test_invalid_code_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown violation code"):
        CovenantViolationError(code="NOT_A_REAL_CODE", detail={})


def test_is_exception() -> None:
    err = CovenantViolationError(code="DENIED_TOOL", detail={"tool": "rm_rf"})
    assert isinstance(err, Exception)


def test_detail_preserved() -> None:
    detail = {"tool": "bash", "declared": ["read_file", "write_file"]}
    err = CovenantViolationError(code="UNDECLARED_TOOL", detail=detail)
    assert err.detail["tool"] == "bash"
    assert "read_file" in err.detail["declared"]
