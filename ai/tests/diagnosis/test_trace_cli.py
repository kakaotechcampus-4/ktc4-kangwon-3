"""로컬 trace CLI: 입력 파일 읽기, 실행 번호, 질문에 답한 재진단 입력, 실행 파일 쓰기를 확인한다.

진단 함수는 결말만 남기는 가짜로 바꿈 (모델·외부 호출 없음).
"""

import json

import pytest

from app.diagnosis import trace_cli
from app.diagnosis.trace_cli import TraceInputError, next_run_name, read_source, replay_run, resume_input, run
from app.dummy.cases import CASES, DummyCaseName
from app.observability.trace import trace_finish, trace_note, trace_step
from app.schemas.callback import PublicQuestionDto
from app.schemas.schemas import ExecutionEndReason
from app.sessions.job import JobDone, JobNeedsInput

QUESTION = PublicQuestionDto(question_key="r1_q1", question_order=1, question_text="배터리로만 동작하나요?")


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def source(tmp_path):
    return _write(tmp_path / "kc-fan.json", {"textBlocks": ["무선 선풍기"], "sourceUrl": "https://example.com/p/1"})


@pytest.fixture
def fake_job(monkeypatch):
    """추출 input·output을 남기고, 첫 실행은 질문하고 멈추고 답이 있으면 끝나는 가짜 진단 함수. 받은 입력을 inputs에."""
    inputs = []

    def job(job_input, context, progress):
        inputs.append(job_input)
        result = CASES[DummyCaseName.KC_FAN].build(job_input.source.product_id)
        with trace_step("extraction"):
            trace_note("input", job_input)
            trace_note("output", result.product)
        if not job_input.answers:
            result = result.model_copy(update={"termination_reason": ExecutionEndReason.USER_INPUT_REQUIRED})
            trace_finish(result.termination_reason.value, result=result, question_round=1, questions=[QUESTION])
            return JobNeedsInput(result, [QUESTION])
        trace_finish(result.termination_reason.value, result=result)
        return JobDone(result)

    monkeypatch.setattr(trace_cli, "build_parts", lambda: None)
    monkeypatch.setattr(trace_cli, "build_job", lambda parts, questions, replay=None: job)
    return inputs


def test_입력_파일은_diagnose_상품_모양으로_읽고_productId가_없으면_파일_이름을_쓴다(source):
    extraction = read_source(source)

    assert (extraction.product_id, extraction.text_blocks, extraction.source_url) == (
        "kc-fan", ["무선 선풍기"], "https://example.com/p/1")


def test_입력이_하나도_없는_파일은_입력_오류(tmp_path):
    with pytest.raises(TraceInputError, match="입력 파일"):
        read_source(_write(tmp_path / "empty.json", {}))


def test_실행_이름은_폴더의_마지막_번호_다음이다(tmp_path):
    assert next_run_name(tmp_path / "없는-폴더") == "run-1"
    for name in ("run-1.json", "run-10.json", "run-2.json", "memo.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    assert next_run_name(tmp_path) == "run-11"


def test_첫_실행은_실행_폴더에_run_1을_쓰고_입력_출처와_결말을_남긴다(source, fake_job, tmp_path):
    out = tmp_path / "traces"

    path = run(source, out, [])

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path == out / "run-1.json"
    assert saved["info"]["source"] == str(source)
    assert saved["finish"]["reason"] == "user_input_required"
    assert fake_job[0].answers == []


def test_답변을_주면_마지막_실행의_결과와_질문으로_재진단_입력을_만들어_다음_번호로_쓴다(source, fake_job, tmp_path):
    out = tmp_path / "traces"
    run(source, out, [])

    path = run(source, out, ["r1_q1=네"])

    resumed = fake_job[1]
    assert path == out / "run-2.json"
    assert resumed.previous is not None
    assert [(a.question_round, a.question_key, a.answer_text) for a in resumed.answers] == [(1, "r1_q1", "네")]
    assert json.loads(path.read_text(encoding="utf-8"))["finish"]["reason"] == "completed"


def test_재진단_입력은_이전_실행까지의_답변을_이어서_붙인다(source, tmp_path):
    out = tmp_path / "traces"
    out.mkdir()
    earlier = {"question_round": 1, "question_key": "r1_q1", "answer_text": "네"}
    result = CASES[DummyCaseName.KC_FAN].build("kc-fan").model_dump(mode="json")
    _write(out / "run-2.json", {
        "steps": [{"id": "s1", "kind": "extraction", "input": {"answers": [earlier]}}],
        "finish": {"reason": "user_input_required", "result": result, "question_round": 2,
                   "questions": [{"question_key": "r2_q1"}]},
    })

    job_input = resume_input(read_source(source), out, ["r2_q1=아니요"])

    assert [(a.question_round, a.question_key) for a in job_input.answers] == [(1, "r1_q1"), (2, "r2_q1")]


@pytest.mark.parametrize(("finish", "answers", "message"), [
    (None, ["r1_q1=네"], "이전 실행"),
    ({"reason": "completed"}, ["r1_q1=네"], "질문하고 멈춘"),
    ({"reason": "user_input_required", "questions": [{"question_key": "r1_q1"}]}, ["r1_q2=네"], "질문 키"),
    ({"reason": "user_input_required", "questions": [{"question_key": "r1_q1"}]}, ["r1_q1"], "질문키=답변"),
])
def test_답할_수_없는_재진단은_입력_오류(source, tmp_path, finish, answers, message):
    if finish is not None:
        _write(tmp_path / "run-1.json", {"steps": [], "finish": finish})

    with pytest.raises(TraceInputError, match=message):
        resume_input(read_source(source), tmp_path, answers)


def test_입력_오류는_종료_코드_2로_알린다(tmp_path, capsys, monkeypatch):
    # 로그 설정은 전역이라 바꾸지 않음 (닫힌 capsys 출력에 핸들러가 남음)
    monkeypatch.setattr(trace_cli, "configure_logging", lambda level: None)

    code = trace_cli.main([str(_write(tmp_path / "empty.json", {}))])

    assert code == 2
    assert "입력 파일" in capsys.readouterr().err


def test_다시_실행은_이전_trace의_입력으로_같은_폴더에_다음_번호를_쓰고_다시_실행_정보를_남긴다(source, fake_job, tmp_path):
    out = tmp_path / "traces"
    first = run(source, out, [])

    path = replay_run(first, "selection", True, first.parent)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert path == out / "run-2.json"
    assert saved["info"]["replay"] == {"from": str(first), "stage": "selection", "only": True}
    assert fake_job[1] == fake_job[0]


@pytest.mark.parametrize("argv", [
    [],
    ["a.json", "--from", "run-1.json", "--stage", "selection"],
    ["--from", "run-1.json"],
    ["--from", "run-1.json", "--stage", "selection", "--answer", "r1_q1=네"],
    ["a.json", "--only"],
])
def test_입력과_다시_실행_옵션을_잘못_섞으면_사용법_오류(argv):
    with pytest.raises(SystemExit) as exc:
        trace_cli.main(argv)

    assert exc.value.code == 2
