"""로컬 진단 trace CLI. 서버·세션·BE 콜백 없이 진단 함수만 돌려 trace 파일을 남김.

    python -m app.diagnosis.trace_cli data/trace-inputs/kc-fan.json
    python -m app.diagnosis.trace_cli data/trace-inputs/kc-fan.json --answer r1_q1=네 --answer r1_q2=아니요

입력 파일은 /diagnose 요청의 상품 하나와 같은 모양 (productId·textBlocks·imageUrls·sourceUrl).
productId가 없으면 파일 이름을 씀.
trace는 실행 폴더(기본 data/traces/<입력 파일 이름>/)에 run-1.json, run-2.json…으로 쌓임.
--answer를 주면 그 폴더의 마지막 실행이 남긴 질문에 답해 재진단. 이전 결과·답변은 마지막 실행 파일에서 읽음.

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

AI_ROOT = Path(__file__).resolve().parents[2]
TRACE_ROOT = AI_ROOT / "data" / "traces"
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
    run_name = next_run_name(directory)
    # 부품 조립은 실행 밖 (모델 설정 오류면 trace 없이 바로 실패)
    job = build_job(build_parts(), build_questions)
    context = ExecutionContext.start(product_id=source.product_id, run_type=RunType.EVALUATION)
    with trace_run(directory, run_name):
        trace_note("source", str(source_path))
        with run_log_context(context):
            outcome = job(job_input, context, _PrintProgress())
    _print_outcome(outcome)
    return directory / f"{run_name}.json"


def _print_outcome(outcome: JobDone | JobNeedsInput | JobFailed) -> None:
    if isinstance(outcome, JobFailed):
        print(f"[결말] 실패 (code={outcome.error_code}, retryable={outcome.retryable})", file=sys.stderr)
        return
    print(f"[결말] {outcome.result.termination_reason.value}", file=sys.stderr)
    if isinstance(outcome, JobNeedsInput):
        for question in outcome.questions:
            print(f"  {question.question_key}: {question.question_text}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="로컬 진단 trace (서버·콜백 없이)")
    parser.add_argument("source", type=Path, help="상품 입력 JSON (/diagnose 상품 하나 모양)")
    parser.add_argument("--out", type=Path, default=None, help="실행 폴더 (기본 data/traces/<입력 파일 이름>)")
    parser.add_argument("--answer", action="append", default=[], metavar="KEY=TEXT",
                        help="마지막 실행 질문에 대한 답변. 질문마다 한 번씩")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    try:
        path = run(args.source, args.out or TRACE_ROOT / args.source.stem, args.answer)
    except TraceInputError as exc:
        print(exc, file=sys.stderr)
        return 2
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
