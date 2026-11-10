"""진단을 LangSmith 실행으로 묶음. LANGSMITH_TRACING을 켠 실행에서만 붙음 (diagnosis/job.py).

채팅 모델 호출은 LangChain이, 판단 모델 호출은 판단 클라이언트(clients/llm/decision/base.py)가 보냄.
여기서는 그 호출을 단계·Tool별로 묶고 이름만 붙임. 진단 실행에는 진단 입력을 Input으로 남김 (#746).
로컬 trace 파일(observability/trace.py)과 별개로 동작함.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from langsmith import trace
from langsmith.utils import tracing_is_enabled

from ..domain.context import ExecutionContext
from ..pipeline.hooks import StageName
from ..schemas.schemas import ToolName
from ..schemas.session import DiagnosisInput
from ..sessions.job import DiagnosisJob, Outcome, ProgressReporter

T = TypeVar("T")

# base64 이미지(data URI)는 한 장에 수백 KB라 앞부분만 남김
DATA_URI_PREFIX = 40


def tracing_on() -> bool:
    """LangSmith 기록을 켠 실행인지 본다.

    Returns:
        bool: 켜져 있으면 True.
    """
    return bool(tracing_is_enabled())


def _traced(name: str, run_type: str, call: Callable[[], T], **options: Any) -> T:
    """호출 하나를 LangSmith 실행 하나로 감싼다.

    Args:
        name: 화면에 보일 이름.
        run_type: LangSmith 실행 종류.
        call: 실제 호출.
        **options: trace 추가 인자.

    Returns:
        T: 호출 결과.
    """
    with trace(name, run_type, **options) as run:
        result = call()
        run.end(outputs={"output": result})
        return result


def stage_hook(stage: StageName, retry_round: int, call: Callable[[], T], /) -> T:
    """단계를 LangSmith 실행으로 감싼다. 재실행 회차는 이름으로 구분함.

    Args:
        stage: 단계 이름.
        retry_round: 회차. 최초 실행은 0.
        call: 실제 단계 호출.

    Returns:
        T: 단계 결과.
    """
    return _traced(f"{stage} #{retry_round}" if retry_round else stage, "chain", call)


def tool_hook(tool_name: ToolName, call: Callable[[], Any], /) -> Any:
    """Tool을 LangSmith 실행으로 감싼다.

    Args:
        tool_name: Tool 이름.
        call: 실제 Tool 호출.

    Returns:
        Any: Tool이 돌려준 값.
    """
    return _traced(f"tool:{tool_name.value}", "tool", call)


def traced_job(job: DiagnosisJob) -> DiagnosisJob:
    """진단 함수 전체를 trace 하나로 묶는다.

    Args:
        job: 진단 함수.

    Returns:
        DiagnosisJob: 같은 일을 하고 LangSmith에 한 묶음으로 남기는 진단 함수.
    """

    def run(job_input: DiagnosisInput, context: ExecutionContext, progress: ProgressReporter) -> Outcome:
        return _traced(
            f"diagnosis:{context.product_id}", "chain", lambda: job(job_input, context, progress),
            inputs=diagnosis_inputs(job_input),
            metadata={"run_id": context.run_id, "run_type": context.run_type.value,
                      "diagnosis_id": context.diagnosis_id},
        )

    return run


def diagnosis_inputs(job_input: DiagnosisInput) -> dict[str, Any]:
    """진단 실행 Input에 남길 진단 입력.

    재진단의 이전 결과 본문은 Output(진단 결과)과 겹쳐 재진단 여부만 남김.

    Args:
        job_input: 진단 함수가 받은 실행 입력.

    Returns:
        dict[str, Any]: 상품 ID, 상품 URL, 상품 글, 이미지 주소(base64는 줄임), 재진단 여부, 답변.
    """
    source = job_input.source
    return {
        "product_id": source.product_id,
        "source_url": source.source_url,
        "text_blocks": source.text_blocks,
        "image_urls": [_short_image(url) for url in source.image_urls],
        "resume": job_input.previous is not None,
        "answers": [answer.model_dump() for answer in job_input.answers],
    }


def _short_image(url: str) -> str:
    """base64 이미지는 앞부분과 길이만 남긴다. http 주소는 그대로.

    Args:
        url: 이미지 주소 또는 data URI.

    Returns:
        str: 기록할 값.
    """
    if not url.startswith("data:"):
        return url
    return f"{url[:DATA_URI_PREFIX]}… ({len(url):,}자)"
