"""로컬 진단 trace CLI. 서버·세션·BE 콜백 없이 진단 함수만 돌려 trace 파일을 남김.

    python -m app.diagnosis.trace_cli logs/trace-inputs/kc-fan.json
    python -m app.diagnosis.trace_cli logs/trace-inputs/kc-fan.json --answer r1_q1=네 --answer r1_q2=아니요

입력 파일은 /diagnose 요청의 상품 하나와 같은 모양 (productId·textBlocks·imageUrls·sourceUrl).
productId가 없으면 파일 이름을 씀.
trace는 실행 폴더(기본 logs/traces/<입력 파일 이름>/)에 run-1.json, run-2.json…으로 쌓임.
--answer를 주면 그 폴더의 마지막 실행이 남긴 질문에 답해 재진단. 이전 결과·답변은 마지막 실행 파일에서 읽음.

단계 다시 실행: 이전 trace의 실행 입력과 앞 단계 결과를 그대로 쓰고 지정한 단계부터 실제로 돌림.
결과는 이전 trace와 같은 폴더에 다음 번호로 쌓임.

    python -m app.diagnosis.trace_cli --from logs/traces/kc-fan/run-1.json --stage selection          # 선택부터 끝까지
    python -m app.diagnosis.trace_cli --from logs/traces/kc-fan/run-1.json --stage selection --only   # 선택만

모델·외부 API는 실제로 부름 (.env 키 필요, 비용 발생). DATABASE_URL이 없으면 관세 Tool은 CLIP만 조회.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError

from ..domain.context import ExecutionContext, PipelineStage, RunType
from ..observability.logs import configure_logging, run_log_context
from ..observability.trace import trace_note, trace_run
from ..routers.diagnose import to_extraction_input
from ..schemas.agent import ExtractionInput
from ..schemas.request import DiagnosisProductInput
from ..schemas.schemas import ExecutionEndReason, FinalAssessment, ToolName
from ..schemas.session import DiagnosisInput, SessionAnswer
from ..sessions.job import JobDone, JobFailed, JobNeedsInput, ToolProgressStatus
from .assembly import build_parts
from .job import build_job
from .questions import build_questions
from .replay import STAGES, ReplayError, ReplayStopped, StageReplay, replay_input

AI_ROOT = Path(__file__).resolve().parents[2]
# 상품 원문·모델 응답 원문이 들어가 git이 무시하는 logs/ 아래
TRACE_ROOT = AI_ROOT / "logs" / "traces"
_RUN_FILE = re.compile(r"run-(\d+)\.json")


class TraceInputError(ValueError):
    """입력 파일·답변·이전 실행을 쓸 수 없는 경우."""


def read_source(path: Path) -> ExtractionInput:
    """입력 파일을 추출 입력으로 읽는다.

    Args:
        path: /diagnose 상품 하나 모양의 JSON 파일. productId가 없으면 파일 이름을 씀.

    Returns:
        ExtractionInput: 추출 입력.

    Raises:
        TraceInputError: JSON이 아니거나 상품 입력 형식이 아닌 경우.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("productId", path.stem)
        return to_extraction_input(DiagnosisProductInput.model_validate(data))
    except (OSError, json.JSONDecodeError, AttributeError, ValidationError) as exc:
        raise TraceInputError(f"입력 파일을 읽지 못했습니다: {path} ({exc})") from exc


def run_files(directory: Path) -> list[Path]:
    """실행 폴더의 run-N.json을 번호 순으로.

    Args:
        directory: 실행 폴더.

    Returns:
        list[Path]: 파일 경로. 폴더가 없으면 빈 목록.
    """
    if not directory.is_dir():
        return []
    numbered = [(int(match.group(1)), path) for path in directory.iterdir()
                if (match := _RUN_FILE.fullmatch(path.name))]
    return [path for _, path in sorted(numbered)]


def next_run_name(directory: Path) -> str:
    """실행 폴더에 새로 쓸 실행 이름. 마지막 번호 다음.

    Args:
        directory: 실행 폴더.

    Returns:
        str: run-N.
    """
    files = run_files(directory)
    last = int(_RUN_FILE.fullmatch(files[-1].name).group(1)) if files else 0
    return f"run-{last + 1}"


def resume_input(source: ExtractionInput, directory: Path, answers: list[str]) -> DiagnosisInput:
    """실행 폴더의 마지막 실행이 남긴 질문에 답한 재진단 입력을 만든다.

    Args:
        source: 원래 입력.
        directory: 실행 폴더.
        answers: ``질문키=답변`` 목록. 마지막 실행의 질문에 모두 답해야 함.

    Returns:
        DiagnosisInput: 이전 결과·지금까지 답변·이번 답변을 담은 입력.

    Raises:
        TraceInputError: 이전 실행이 없거나 질문하고 멈춘 실행이 아닌 경우, 답변이 질문과 맞지 않는 경우.
    """
    files = run_files(directory)
    if not files:
        raise TraceInputError(f"답할 이전 실행이 없습니다: {directory}")
    last = json.loads(files[-1].read_text(encoding="utf-8"))
    finish = last.get("finish") or {}
    if finish.get("reason") != ExecutionEndReason.USER_INPUT_REQUIRED.value:
        raise TraceInputError(f"마지막 실행이 질문하고 멈춘 실행이 아닙니다: {files[-1].name} ({finish.get('reason')})")
    given = dict(_split_answer(answer) for answer in answers)
    asked = [question["question_key"] for question in finish["questions"]]
    if set(given) != set(asked):
        raise TraceInputError(f"질문 키와 답변이 맞지 않습니다. 질문: {', '.join(asked)}")
    extraction = next(step for step in last["steps"] if step["kind"] == "extraction")
    earlier = [SessionAnswer.model_validate(answer) for answer in extraction["input"]["answers"]]
    current = [SessionAnswer(question_round=finish["question_round"], question_key=key, answer_text=given[key])
               for key in asked]
    return DiagnosisInput(source=source, previous=FinalAssessment.model_validate(finish["result"]),
                          answers=earlier + current)


def _split_answer(answer: str) -> tuple[str, str]:
    key, separator, text = answer.partition("=")
    if not separator or not key.strip() or not text.strip():
        raise TraceInputError(f"답변은 질문키=답변 모양이어야 합니다: {answer}")
    return key.strip(), text.strip()


class _PrintProgress:
    """진행 알림을 터미널에 한 줄씩 찍음."""

    def stage(self, stage: PipelineStage) -> None:
        print(f"[단계] {stage.value}", file=sys.stderr)

    def tool(self, tool_name: ToolName, status: ToolProgressStatus) -> None:
        print(f"  [Tool] {tool_name.value} {status}", file=sys.stderr)


def run(source_path: Path, directory: Path, answers: list[str]) -> Path:
    """진단 한 건을 trace로 남기며 돌린다.

    Args:
        source_path: 입력 파일.
        directory: 실행 폴더.
        answers: 재진단 답변 (``질문키=답변``). 비었으면 첫 실행.

    Returns:
        Path: 쓴 trace 파일.

    Raises:
        TraceInputError: 입력·답변·이전 실행을 쓸 수 없는 경우.
    """
    source = read_source(source_path)
    job_input = resume_input(source, directory, answers) if answers else DiagnosisInput(source=source)
    return _execute(job_input, directory, {"source": str(source_path)})


def replay_run(trace_path: Path, stage: str, only: bool, directory: Path) -> Path:
    """이전 trace의 입력·앞 단계 결과로 지정한 단계부터 다시 돌린다.

    Args:
        trace_path: 이전 실행의 trace 파일.
        stage: 실제로 돌리기 시작할 단계.
        only: 그 단계 하나만 돌리고 멈출지.
        directory: 실행 폴더.

    Returns:
        Path: 쓴 trace 파일.

    Raises:
        TraceInputError: trace 파일을 읽지 못한 경우.
        ReplayError: 다시 실행할 수 없는 trace인 경우.
    """
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceInputError(f"trace 파일을 읽지 못했습니다: {trace_path} ({exc})") from exc
    replay = StageReplay.from_trace(trace, stage, only)
    info = {"replay": {"from": str(trace_path), "stage": stage, "only": only}}
    return _execute(replay_input(trace), directory, info, replay)


def _execute(job_input: DiagnosisInput, directory: Path, info: dict, replay: StageReplay | None = None) -> Path:
    """진단 함수를 trace로 감싸 돌리고 결말을 찍는다.

    Args:
        job_input: 실행 입력.
        directory: 실행 폴더.
        info: trace 실행 정보에 남길 값 (입력 출처 등).
        replay: 단계 다시 실행 설정. 없으면 처음부터.

    Returns:
        Path: 쓴 trace 파일.
    """
    run_name = next_run_name(directory)
    # 부품 조립은 실행 밖 (모델 설정 오류면 trace 없이 바로 실패)
    job = build_job(build_parts(), build_questions, replay)
    context = ExecutionContext.start(product_id=job_input.source.product_id, run_type=RunType.EVALUATION)
    with trace_run(directory, run_name):
        for key, value in info.items():
            trace_note(key, value)
        with run_log_context(context):
            try:
                outcome = job(job_input, context, _PrintProgress())
            except ReplayStopped as exc:
                outcome = exc
    _print_outcome(outcome)
    return directory / f"{run_name}.json"


def _print_outcome(outcome: JobDone | JobNeedsInput | JobFailed | ReplayStopped) -> None:
    if isinstance(outcome, ReplayStopped):
        print(f"[결말] {outcome.stage} 단계만 다시 실행하고 멈춤", file=sys.stderr)
        return
    if isinstance(outcome, JobFailed):
        print(f"[결말] 실패 (code={outcome.error_code}, retryable={outcome.retryable})", file=sys.stderr)
        return
    print(f"[결말] {outcome.result.termination_reason.value}", file=sys.stderr)
    if isinstance(outcome, JobNeedsInput):
        for question in outcome.questions:
            print(f"  {question.question_key}: {question.question_text}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="로컬 진단 trace (서버·콜백 없이)")
    parser.add_argument("source", type=Path, nargs="?", help="상품 입력 JSON (/diagnose 상품 하나 모양)")
    parser.add_argument("--out", type=Path, default=None,
                        help="실행 폴더 (기본: 입력이면 logs/traces/<입력 파일 이름>, --from이면 그 trace 폴더)")
    parser.add_argument("--answer", action="append", default=[], metavar="KEY=TEXT",
                        help="마지막 실행 질문에 대한 답변. 질문마다 한 번씩")
    parser.add_argument("--from", dest="from_trace", type=Path, default=None, help="다시 실행할 이전 trace 파일")
    parser.add_argument("--stage", choices=STAGES, default=None, help="다시 실행을 시작할 단계 (--from과 같이)")
    parser.add_argument("--only", action="store_true", help="시작 단계 하나만 돌리고 멈춤 (--from과 같이)")
    args = parser.parse_args(argv)
    if (args.source is None) == (args.from_trace is None):
        parser.error("입력 파일과 --from 중 하나만 주세요")
    if args.from_trace is not None and (args.stage is None or args.answer):
        parser.error("--from에는 --stage가 필요하고 --answer는 쓸 수 없습니다")
    if args.from_trace is None and (args.stage is not None or args.only):
        parser.error("--stage·--only는 --from과 같이 씁니다")
    configure_logging("INFO")
    try:
        if args.from_trace is not None:
            path = replay_run(args.from_trace, args.stage, args.only, args.out or args.from_trace.parent)
        else:
            path = run(args.source, args.out or TRACE_ROOT / args.source.stem, args.answer)
    except (TraceInputError, ReplayError) as exc:
        print(exc, file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
