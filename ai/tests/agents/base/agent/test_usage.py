"""BaseAgent 사용량 기록: 호출 1건당 1행, 기록 이름·모델·추론 강도 (#160, #284, #311)."""

from time import perf_counter

from app.observability.agent_sinks import agent_sinks
from app.schemas.clients.decision_request import YesNoQuestion
from app.usage import CallUsage


def test_성공하면_사용량을_한_번_기록한다(fakes, stub_model, records):
    fakes.Agent(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    assert len(records) == 1
    row = records[0]
    assert (row["agent"], row["subject_id"], row["ok"], row["error_type"]) == ("fake", "p-1", True, None)
    assert row["configured_model"] == "openai/gpt-4.1-mini"
    assert (row["usage"].input_tokens, row["usage"].cached_tokens, row["usage"].output_tokens) == (100, 40, 20)


def test_사용량_기록과_실행_정보는_같은_측정값을_쓴다(fakes, stub_model, records):
    meta = fakes.Agent(stub_model(fakes.Answer(value="ok"))).run_with_meta(fakes.question).meta

    assert (meta.usage, meta.elapsed_ms) == (records[0]["usage"], records[0]["elapsed_ms"])


def test_usage_agent와_configured_model을_넘기면_그_이름으로_기록한다(fakes, stub_model, records):
    model = stub_model(fakes.Answer(value="ok"))

    fakes.Agent(model, usage_agent="fake-eval", configured_model="custom").run(fakes.question)

    assert (records[0]["agent"], records[0]["configured_model"]) == ("fake-eval", "custom")


def test_모델의_추론_강도를_사용량_기록에_남긴다(fakes, stub_model, records):
    reasoning = stub_model(fakes.Answer(value="ok"))
    reasoning.reasoning_effort = "low"

    fakes.Agent(reasoning).run(fakes.question)
    fakes.Agent(stub_model(fakes.Answer(value="ok"))).run(fakes.question)

    assert [record["reasoning_effort"] for record in records] == ["low", None]


def test_호출이_끝나면_등록된_sink에_실행_정보와_기록_대상을_넘긴다(fakes, stub_model, records):
    received = []

    with agent_sinks.added(lambda meta, subject_id: received.append((meta, subject_id))):
        result = fakes.Agent(stub_model(fakes.Answer(value="ok")), usage_agent="fake-eval").run_with_meta(fakes.question)

    assert received == [(result.meta, "p-1")]
    assert (result.meta.component, result.meta.usage_name) == ("fake", "fake-eval")


def test_판단_모델_호출_기록은_판단_모델_이름과_단가로_남기고_추론_강도는_비운다(fakes, stub_model, records):
    model = stub_model(fakes.Answer(value="ok"))
    model.reasoning_effort = "low"
    agent = fakes.Agent(model, decision_client=object(), decision_model="typesafe/jev-latest")
    usage = CallUsage("typesafe/jev-1.14-20261014", input_tokens=1_000_000, cached_tokens=0, output_tokens=0)
    questions = [YesNoQuestion(name="kind_kids", instructions="어린이가 주로 쓰는 종류인가")]

    meta = agent._finish_call(usage, "p-1", perf_counter(), decision_questions=questions)

    assert (meta.model, meta.reasoning_effort, meta.cost_krw) == ("typesafe/jev-latest", None, 64.0)
    assert (records[0]["configured_model"], records[0]["reasoning_effort"]) == ("typesafe/jev-latest", None)
