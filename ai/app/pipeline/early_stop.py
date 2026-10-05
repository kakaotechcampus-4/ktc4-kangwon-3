"""실행 메타데이터를 제외한 구조적 동일성으로 재실행의 개선 여부를 비교한다.

자유 문장의 의미를 추론하지 않는다. 표현만 달라도 변화로 취급하며,
확인할 수 없는 실행 기록이나 finding 참조로 조기 중단하지 않는다.
"""

import json
from typing import Any

from ..schemas.pipeline import SelectionResult
from ..schemas.schemas import (
    ToolName,
    ToolResult,
    ToolStatus,
    VerificationResult,
    VerificationStatus,
)


def _canonical(value: Any) -> str:
    """집합 성격의 목록만 정렬하고, HS 후보 순서·중복·문자열은 보존한다."""
    def normalize(item: Any, *, preserve_order: bool = False) -> Any:
        if isinstance(item, dict):
            return {
                key: normalize(val, preserve_order=key == "hs_code_candidates")
                for key, val in item.items()
            }
        if isinstance(item, list):
            normalized = [normalize(val) for val in item]
            return normalized if preserve_order else sorted(normalized, key=encode)
        return item

    def encode(item: Any) -> str:
        return json.dumps(item, sort_keys=True, ensure_ascii=False)

    return encode(normalize(value))


def _normal_execution(result: ToolResult) -> bool:
    return (
        result.selected
        and result.status in {ToolStatus.SUCCESS, ToolStatus.PARTIAL}
        and result.error is None
        and result.result is not None
        and bool(result.findings)
    )


def _normal_execution_record(
    state: SelectionResult,
    name: ToolName | str,
) -> ToolResult | None:
    """최신 유효 상태와 일치하는 마지막 정상 실행 기록을 가져온다."""
    latest = [result for result in state.tool_results if result.tool_name == name]
    history = [result for result in state.tool_result_history if result.tool_name == name]
    if len(latest) != 1 or not history:
        return None
    actual = history[-1]
    if (
        not _normal_execution(latest[0])
        or not _normal_execution(actual)
        or not actual.execution_id
        or actual.retry_round != latest[0].retry_round
        or actual.execution_id != latest[0].execution_id
    ):
        return None
    return actual


def _snapshot(
    selection_result: SelectionResult,
    verification: VerificationResult,
) -> str | None:
    """finding ID를 내용으로 치환한다. 참조가 불명확하면 비교 불가로 처리한다."""
    finding_keys: dict[str, str] = {}
    tools = []
    for result in selection_result.tool_results:
        tool_data = result.model_dump(mode="json", exclude={
            "execution_id", "retry_round", "executed_at", "selection_reason",
            "query", "raw_response", "findings",
        })
        findings = []
        for finding in result.findings:
            content = finding.model_dump(mode="json", exclude={"finding_id"})
            if finding.finding_id in finding_keys:
                return None
            finding_keys[finding.finding_id] = _canonical(content)
            findings.append(content)
        tool_data["findings"] = findings
        tools.append(tool_data)

    def resolve(ids: list[str]) -> list[str] | None:
        if any(identifier not in finding_keys for identifier in ids):
            return None
        return [finding_keys[identifier] for identifier in ids]

    checked = resolve(verification.checked_finding_ids)
    if checked is None:
        return None
    issues = []
    for issue in verification.issues:
        related = resolve(issue.related_finding_ids)
        if related is None:
            return None
        issue_data = issue.model_dump(mode="json", exclude={"issue_id", "related_finding_ids"})
        issue_data["related_findings"] = related
        issues.append(issue_data)
    verification_data = verification.model_dump(mode="json", exclude={
        "verified_at", "issues", "checked_finding_ids", "follow_up_questions",
    })
    verification_data["issues"] = issues
    verification_data["checked_findings"] = checked
    verification_data["follow_up_questions"] = [
        question.model_dump(mode="json", exclude={"question_id"})
        for question in verification.follow_up_questions
    ]
    return _canonical({"tools": tools, "verification": verification_data})


def has_no_progress(
    previous: SelectionResult,
    previous_verification: VerificationResult,
    current: SelectionResult,
    current_verification: VerificationResult,
    *,
    executed_tools: list[ToolName | str],
    retry_round: int,
) -> bool:
    """인접한 두 정상 실행의 판단·근거·검증 결과가 그대로인지 확인한다.

    최초 결과도 비교 기준으로 사용한다. 실패 직후에는 중단하지 않고,
    다음 정상 실행 결과를 새 기준으로 삼는다. 횟수 제한·종료 처리는 Runner 책임이다.
    """
    if (
        previous_verification.status is not VerificationStatus.TOOLS_REQUIRED
        or current_verification.status is not VerificationStatus.TOOLS_REQUIRED
        or not executed_tools
        or len(set(executed_tools)) != len(executed_tools)
        or set(executed_tools) != set(previous_verification.additional_tools_required)
        or isinstance(retry_round, bool)
        or not isinstance(retry_round, int)
        or retry_round < 1
    ):
        return False

    # 유효한 최신 상태뿐 아니라 두 회차의 실제 실행 기록도 확인한다.
    for name in executed_tools:
        previous_execution = _normal_execution_record(previous, name)
        current_execution = _normal_execution_record(current, name)
        if previous_execution is None or current_execution is None:
            return False
        if previous_execution.retry_round >= retry_round:
            return False
        if current_execution.retry_round != retry_round:
            return False

    before = _snapshot(previous, previous_verification)
    after = _snapshot(current, current_verification)
    return before is not None and after is not None and before == after
