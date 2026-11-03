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


def test_성공한_호출은_메시지·출력·실행_정보를_호출_파일로_남기고_단계엔_요약만_넣는다(fakes, stub_model, records, tmp_path):
    with trace_run(tmp_path) as recorder:
        with trace_step("selection") as step:
            fakes.Agent(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    summary = step["calls"][0]
    assert (summary["id"], summary["component"], summary["file"]) == ("c1", "fake", "run-1/calls/c1.json")
    assert summary["model"] == "openai/gpt-4.1-mini" and "error_type" not in summary
    call = _read(tmp_path / summary["file"])
    system, human = call["request"]
    assert (tmp_path / system["prompt_file"]).read_text(encoding="utf-8") == get_prompt(PromptName.EXTRACTION).text
    assert human == {"role": "human", "content": "질문"}
    assert call["output"] == {"value": "ok"}
    assert call["meta"]["usage"]["input_tokens"] == 100
    assert recorder.info == {}


def test_같은_시스템_프롬프트는_호출이_여러_번이어도_파일_하나로_남긴다(fakes, stub_model, records, tmp_path):
    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")))
    with trace_run(tmp_path) as recorder:
        agent.run(fakes.question)
        agent.run(fakes.question)

    assert [call["id"] for call in recorder.info["calls"]] == ["c1", "c2"]
    assert len(list((tmp_path / "prompts").iterdir())) == 1


def test_해석에_실패한_호출은_응답_본문과_실패_단계를_남긴다(fakes, stub_model, records, tmp_path):
    with trace_run(tmp_path) as recorder:
        with pytest.raises(fakes.Error):
            fakes.Agent(stub_model('{"value": ')).run(fakes.question)

    summary = recorder.info["calls"][0]
    assert summary["failure_phase"] == "parsing"
    call = _read(tmp_path / summary["file"])
    assert (call["output"], call["raw"]) == (None, '{"value": ')


def test_이미지는_링크만_남기고_data_URI는_본문을_뺀다(fakes, stub_model, records, tmp_path):
    data_uri = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8").decode()
    blocks = [{"type": "text", "text": "사진"}, {"type": "image_url", "image_url": {"url": data_uri}},
              {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}}]
    agent = fakes.Agent(stub_model(fakes.Answer(value="ok")))
    with trace_run(tmp_path):
        agent._invoke_with_meta([HumanMessage(content=blocks)], subject_id="p-1")

    assert _read(tmp_path / "run-1/calls/c1.json")["request"][0]["content"] == [
        {"type": "text", "text": "사진"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,…(생략)"}},
        {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}},
    ]
    assert not (tmp_path / "run-1/images").exists()


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

    call = _read(tmp_path / recorder.info["calls"][0]["file"])
    assert call["request"]["subject"] == {"product_name": "색연필"}
    assert call["request"]["questions"][0]["name"] == "kind_kids"
    assert call["output"]["answers"]["kind_kids"] is not None
    assert call["meta"]["model"] == "typesafe/jev-latest"
