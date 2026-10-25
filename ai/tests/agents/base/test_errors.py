"""에이전트 공통 예외. 모든 에이전트 예외는 AgentError(=RuntimeError)로 잡힌다(#231)."""

import pytest

from app.agents.base import AgentError, AgentRunMeta


class _FakeError(AgentError):
    pass


def test_에이전트_예외는_AgentError와_RuntimeError로도_잡힌다():
    with pytest.raises(AgentError):
        raise _FakeError("x")
    with pytest.raises(RuntimeError):
        raise _FakeError("x")


def test_부분_결과와_실행_정보를_담는다():
    meta = AgentRunMeta(component="fake", error_type="TimeoutError")

    error = _FakeError("실패", partial_result={"rules": 1}, meta=meta)

    assert (str(error), error.partial_result, error.meta) == ("실패", {"rules": 1}, meta)
    assert (_FakeError("실패").partial_result, _FakeError("실패").meta) == (None, None)
