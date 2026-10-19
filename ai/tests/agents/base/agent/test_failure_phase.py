"""실패 단계 기록: call·parsing·finalize를 사용량 행과 실행 정보에 남기고, 후처리 실패도 실패 1행으로 (모니터링용)."""

import pytest


class _Wrapped(Exception):
    pass


@pytest.mark.parametrize(("model_args", "phase"), [
    ({"error": TimeoutError()}, "call"),
    ({"reply": {"wrong": 1}}, "parsing"),
])
def test_호출·파싱_실패는_그_단계로_기록한다(fakes, stub_model, records, model_args, phase):
    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(stub_model(**model_args)).run(fakes.question)

    assert (records[0]["ok"], records[0]["failure_phase"]) == (False, phase)
    assert caught.value.meta.failure_phase == phase


def test_성공은_후처리까지_끝난_뒤_단계_없이_한_번_기록한다(fakes, stub_model, records):
    meta = fakes.Agent(stub_model(fakes.Answer(value="ok"))).run_with_meta(fakes.question).meta

    assert [(row["ok"], row["failure_phase"]) for row in records] == [(True, None)]
    assert meta.failure_phase is None


def test_후처리에서_에이전트_예외가_나면_토큰을_남긴_finalize_실패로_기록한다(fakes, stub_model, records):
    class _Rejecting(fakes.Agent):
        def _finalize(self, output, input):
            raise fakes.Error("입력에 없는 번호")

    with pytest.raises(fakes.Error) as caught:
        _Rejecting(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    assert len(records) == 1
    row = records[0]
    assert (row["ok"], row["failure_phase"], row["error_type"]) == (False, "finalize", "FakeError")
    assert row["usage"].input_tokens == 100
    # 예외에도 실행 정보를 담아 호출부가 비용·단계를 볼 수 있음
    assert (caught.value.meta.failure_phase, caught.value.meta.usage.input_tokens) == ("finalize", 100)


def test_에이전트_예외가_원인을_감싸면_원인_이름으로_기록한다(fakes, stub_model, records):
    class _Wrapping(fakes.Agent):
        def _finalize(self, output, input):
            raise fakes.Error("후처리 실패") from _Wrapped()

    with pytest.raises(fakes.Error):
        _Wrapping(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    assert records[0]["error_type"] == "_Wrapped"


def test_후처리의_코드_오류는_감싸지_않고_그대로_던지되_실패로_기록한다(fakes, stub_model, records):
    class _Buggy(fakes.Agent):
        def _finalize(self, output, input):
            return {}["없는 키"]

    with pytest.raises(KeyError):
        _Buggy(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    assert (records[0]["ok"], records[0]["failure_phase"], records[0]["error_type"]) == (False, "finalize", "KeyError")
