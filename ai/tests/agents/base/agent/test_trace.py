"""BaseAgent trace 기록: 모델 호출마다 보낸 메시지·출력·실행 정보를 호출 파일로, 단계에는 요약만 남긴다."""

import base64
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage

from app.clients.llm.decision import TypeSafeDecisionClient
from app.observability.trace import trace_run, trace_step
from app.prompts import PromptName, get_prompt
from app.schemas.clients.decision_request import YesNoQuestion

def _read(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_기록_중이_아니면_파일을_쓰지_않는다(fakes, stub_model, records, tmp_path):
    fakes.Agent(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    assert list(tmp_path.iterdir()) == []


def test_성공한_호출은_메시지·출력·실행_정보를_열린_단계의_calls에_원문째_남긴다(fakes, stub_model, records, tmp_path):
    with trace_run(tmp_path) as recorder:
        with trace_step("selection") as step:
            fakes.Agent(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    [call] = step["calls"]
    assert (call["id"], call["component"]) == ("c1", "fake")
    system, human = call["request"]
    assert recorder.prompts[system["prompt"]] == get_prompt(PromptName.EXTRACTION).text
    assert human == {"role": "human", "content": "질문"}
    assert call["output"] == {"value": "ok"}
    assert call["meta"]["model"] == "openai/gpt-4.1-mini" and call["meta"]["error_type"] is None
    assert call["meta"]["usage"]["input_tokens"] == 100
    assert recorder.info == {}
    assert _read(tmp_path / "run-1.json")["steps"][0]["calls"] == [call]


def test_같은_시스템_프롬프트는_호출이_여러_번이어도_한_번만_남긴다(fakes, stub_model, records, tmp_path):
    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")))
    with trace_run(tmp_path) as recorder:
        agent.run(fakes.question)
        agent.run(fakes.question)

    first, second = recorder.info["calls"]
    assert (first["id"], second["id"]) == ("c1", "c2")
    assert first["request"][0] == second["request"][0]
    assert len(recorder.prompts) == 1


def test_해석에_실패한_호출은_응답_본문과_실패_단계를_남긴다(fakes, stub_model, records, tmp_path):
    with trace_run(tmp_path) as recorder:
        with pytest.raises(fakes.Error):
            fakes.Agent(stub_model('{"value": ')).run(fakes.question)

    [call] = recorder.info["calls"]
    assert call["meta"]["failure_phase"] == "parsing"
    assert (call["output"], call["raw"]) == (None, '{"value": ')


def test_이미지는_링크만_남기고_data_URI는_본문을_뺀다(fakes, stub_model, records, tmp_path):
    data_uri = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8").decode()
    blocks = [{"type": "text", "text": "사진"}, {"type": "image_url", "image_url": {"url": data_uri}},
              {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}}]
    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")))
    with trace_run(tmp_path) as recorder:
        agent._invoke_with_meta([HumanMessage(content=blocks)], subject_id="p-1")

    assert recorder.info["calls"][0]["request"][0]["content"] == [
        {"type": "text", "text": "사진"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,…(생략)"}},
        {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}},
    ]


def test_판단_호출은_요청과_질문별_답을_남긴다(fakes, stub_model, records, tmp_path):
    reply = {"model": "typesafe/jev-1", "answers": {"kind_kids": {"type": "noul", "noul": 0.61}},
             "usage": {"input_tokens": 10, "output_tokens": 0, "cached_prompt_tokens": 0, "cache_write_tokens": 0}}
    client = TypeSafeDecisionClient("https://gateway.test/v1", "test-key",
                                    transport=httpx.MockTransport(lambda request: httpx.Response(200, json=reply)))
    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")), decision_client=client,
                        decision_model="typesafe/jev-latest")
    questions = [YesNoQuestion(name="kind_kids", instructions="어린이가 주로 쓰는 종류인가")]

    with trace_run(tmp_path) as recorder:
        _, usage, started_at = agent._call_decision({"product_name": "색연필"}, questions, subject_id="p-1")
        agent._finish_call(usage, "p-1", started_at, decision_questions=questions)

    [call] = recorder.info["calls"]
    assert call["request"]["subject"] == {"product_name": "색연필"}
    assert call["request"]["questions"][0]["name"] == "kind_kids"
    assert call["output"]["answers"]["kind_kids"] is not None
    assert call["meta"]["model"] == "typesafe/jev-latest"


def test_응답을_못_받은_호출은_실패_원인을_남기고_단계와_결말이_그_호출을_가리킨다(fakes, stub_model, records, tmp_path):
    with pytest.raises(fakes.Error):
        with trace_run(tmp_path) as recorder:
            with trace_step("selection"):
                fakes.Agent(stub_model(error=RuntimeError("timeout"))).run(fakes.question)

    [step] = recorder.steps
    [call] = step["calls"]
    assert call["error"] == {"type": "RuntimeError", "message": "timeout"}
    assert "output" not in call
    assert step["error"]["call"] == "c1"
    assert step["error"]["cause"] == {"type": "RuntimeError", "message": "timeout"}
    assert recorder.finish["at"] == {"step": "s1", "kind": "selection", "path": ["s1"], "call": "c1"}


def test_후처리_실패도_출력과_실패_원인을_같이_남긴다(fakes, stub_model, records, tmp_path):
    class _Failing(fakes.Agent):
        def _finalize(self, output, input):
            raise ValueError("없는 이미지 번호")

    with trace_run(tmp_path) as recorder:
        with pytest.raises(ValueError):
            _Failing(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    [call] = recorder.info["calls"]
    assert call["output"] == {"value": "ok"}
    assert call["error"] == {"type": "ValueError", "message": "없는 이미지 번호"}
    assert call["meta"]["failure_phase"] == "finalize"


def test_길이_초과로_잘린_응답은_받은_본문을_남긴다(fakes, records, fake_gateway, tmp_path):
    with trace_run(tmp_path) as recorder:
        with pytest.raises(fakes.Error):
            fakes.Agent(fake_gateway('{"value": "잘린', "length", [])).run(fakes.question)

    [call] = recorder.info["calls"]
    assert call["raw"] == '{"value": "잘린'
    assert call["error"]["type"] == "LengthFinishReasonError"
    assert call["meta"]["failure_phase"] == "parsing"


def test_단계_밖에서_실패한_호출도_결말이_그_호출을_가리킨다(fakes, stub_model, records, tmp_path):
    with pytest.raises(fakes.Error):
        with trace_run(tmp_path) as recorder:
            fakes.Agent(stub_model(error=RuntimeError("timeout"))).run(fakes.question)

    assert recorder.finish["at"] == {"step": None, "kind": None, "path": [], "call": "c1"}
