"""실제 ChatOpenAI + 가짜 게이트웨이(스트리밍, 네트워크로 나가지 않음)로 SDK 경로를 확인한다 (#284).

스트리밍 중 SDK가 출력을 먼저 파싱하다 사용량을 잃던 문제를 막으려고 Base가 스키마를 dict로 넘기고 직접 검증함.
"""

import contextlib

import pytest

from app.agents.base import AgentError


def test_SDK_스트리밍_경로에서도_출력과_사용량을_돌려준다(fakes, records, fake_gateway):
    assert fakes.Strict(fake_gateway('{"value": "ok"}', "stop", [])).run(fakes.question) == "OK"
    assert (records[0]["ok"], records[0]["usage"].input_tokens) == (True, 1000)


@pytest.mark.parametrize("agent_name", ["Agent", "Strict", "Rich", "StrictRich"])
def test_SDK가_변환한_스키마의_요청_본문은_클래스를_넘길_때와_같다(fakes, records, fake_gateway, agent_name):
    # Base는 SDK 비공개 함수(type_to_response_format_param)로 스키마를 dict로 넘김.
    # SDK를 올려 요청이 달라지면 여기서 실패
    agent_class = getattr(fakes, agent_name)
    expected: list[dict] = []
    reference = fake_gateway("{}", "stop", expected).with_structured_output(
        agent_class.output_schema, include_raw=True, **agent_class.structured_output_options,
    )
    # 응답이 스키마와 맞지 않아 SDK가 파싱 중 예외를 내지만 요청은 이미 기록됨
    with contextlib.suppress(Exception):
        reference.invoke(fakes.RulesOnly()._build_messages(fakes.question))

    actual: list[dict] = []
    with pytest.raises(AgentError):
        agent_class(fake_gateway("{}", "stop", actual)).run(fakes.question)

    assert actual == expected


@pytest.mark.parametrize(
    ("content", "finish", "cause"),
    [
        ("이건 JSON이 아님", "stop", "ValidationError"),
        # 잘린 JSON·코드블록·뒤에 붙은 설명은 보정해 받아들이지 않음 (엄격한 JSON)
        ('{"value": "ok"', "stop", "ValidationError"),
        ('```json\n{"value": "ok"}\n```', "stop", "ValidationError"),
        ('{"value": "ok"}\n위와 같이 판단했습니다.', "stop", "ValidationError"),
        ('{"wrong": 1}', "stop", "ValidationError"),
        ('{"value": "잘린', "length", "LengthFinishReasonError"),
        ('{"value": "ok"}', "content_filter", "ContentFilterFinishReasonError"),
    ],
)
def test_스트리밍_출력이_틀려도_토큰을_기록하고_파싱_실패로_감싼다(fakes, records, fake_gateway, content, finish, cause):
    requests: list[dict] = []

    with pytest.raises(fakes.Error, match="스키마와 맞지 않습니다") as caught:
        fakes.Agent(fake_gateway(content, finish, requests)).run(fakes.question)

    assert type(caught.value.__cause__).__name__ == cause
    assert len(requests) == 1
    assert len(records) == 1
    assert (records[0]["ok"], records[0]["error_type"]) == (False, cause)
    assert (records[0]["usage"].input_tokens, records[0]["usage"].output_tokens) == (1000, 100)


def test_모델이_거절하면_토큰을_기록하고_OpenAIRefusalError를_원인으로_연결한다(fakes, records, fake_gateway):
    with pytest.raises(fakes.Error) as caught:
        fakes.Agent(fake_gateway(None, "stop", [], refusal="처리할 수 없습니다.")).run(fakes.question)

    assert type(caught.value.__cause__).__name__ == "OpenAIRefusalError"
    assert (records[0]["error_type"], records[0]["usage"].input_tokens) == ("OpenAIRefusalError", 1000)


def test_빈_응답도_토큰을_기록하고_파싱_실패로_감싼다(fakes, records, fake_gateway):
    with pytest.raises(fakes.Error, match="스키마와 맞지 않습니다"):
        fakes.Agent(fake_gateway("", "stop", [])).run(fakes.question)

    assert (records[0]["ok"], records[0]["usage"].input_tokens) == (False, 1000)
