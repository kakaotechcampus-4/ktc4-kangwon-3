"""규칙 검사와 모델 검토를 결합해 심사 초안을 검증한다.

``verify(DraftAssessment) -> VerificationResult`` 계약은 그대로 유지한다.
툴 재실행과 재시도 제한은 파이프라인의 책임이며 이 모듈은 판단만 돌려준다.
"""

import json

from ...prompts import PromptName
from ...schemas.base import utc_now
from ...schemas.schemas import (
    DraftAssessment,
    FollowUpQuestion,
    TraceEvent,
    VerificationIssue,
    VerificationIssueType as IssueType,
    VerificationResult,
    VerificationStatus as Status,
)
from ..base import AgentError, BaseAgent, ModelFailurePhase
from .rules import run_rule_checks
from .schemas import _Review

# 추가 Tool 실행으로 보완할 수 있는 검증 이슈이다.
_TOOL_RECOVERABLE_ISSUES = frozenset(
    {
        IssueType.TOOL_FAILURE,
        IssueType.MISSING_EVIDENCE,
    }
)


class VerificationError(AgentError):
    """모델 검증을 완료하지 못했다.

    ``partial_result``에는 모델 호출 전 완료한 규칙 검사 결과(VerificationResult)를 보존할 수 있다.
    파이프라인은 이를 ``FinalVerificationStatus.INCOMPLETE`` 결과에 포함하고,
    정상 검증 완료로 취급하지 않아야 한다.
    """


class VerificationAgent(BaseAgent[_Review]):
    """종합된 심사 결과의 근거·누락·모순을 검증한다.

    생성자는 BaseAgent 그대로. model을 주입하면 테스트에서 실제 API 호출 없이 검증할 수 있음.
    model 없이도 verify_rules()는 동작하고, verify()는 명시적으로 실패함 (모델 자동 생성 안 함).
    """

    component_name = "verification"
    prompt_name = PromptName.VERIFICATION
    output_schema = _Review
    error_class = VerificationError
    # 프록시가 strict json_schema를 지원하므로 함수호출 방식 대신 스키마를 강제함
    structured_output_options = {"method": "json_schema", "strict": True}
    # 규칙 전용 실행(verify_rules)은 모델이 필요 없어 자동 생성하지 않음. 모델은 from_env()로
    creates_default_model = False

    @classmethod
    def from_env(cls) -> "VerificationAgent":
        from ...config import build_agent_model

        return cls(build_agent_model(cls.component_name))

    def _review_with_trace(
        self,
        messages: list[dict[str, str]],
        *,
        subject_id: str,
        rules: VerificationResult,
        trace: list[TraceEvent] | None,
    ) -> _Review:
        """모델 검토를 호출하고, 실패하면 기존 Trace를 남긴 뒤 같은 예외를 다시 던진다 (#171 §4.2).

        Args:
            messages: 모델에 보낼 메시지.
            subject_id: 사용량 기록 대상 상품 ID.
            rules: 규칙 검사 결과. 실패 시 VerificationError.partial_result로 보존.
            trace: 실행 이력. None이면 기록하지 않음.

        Returns:
            _Review: 모델 검토 결과.

        Raises:
            VerificationError: 모델 호출 또는 파싱 실패. 원인은 ``__cause__``에 보존.
        """
        try:
            return self._invoke(messages, subject_id=subject_id, partial_result=rules)
        except VerificationError as exc:
            cause = exc.__cause__
            self._append_trace(
                trace,
                action="model_review_failed",
                status="failed",
                detail=f"_Review 생성 실패: {type(cause).__name__}",
            )
            # 새 예외로 감싸지 않아 원본 원인이 __cause__에 그대로 남음
            raise

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """기존 검토 호출 실패 문구를 돌려준다.

        include_raw 이전에는 파싱 실패도 invoke 예외로 와서 같은 문구였음. 호출·파싱 구분은
        사용량 기록의 error_type과 ``__cause__``로 확인.
        응답 본문이 메시지에 섞일 수 있어 이 메시지를 그대로 외부에 공유하지 않음.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        return f"모델 검토 호출에 실패했습니다: {type(cause).__name__}: {cause}"

    def verify(
        self,
        draft: DraftAssessment,
        *,
        trace: list[TraceEvent] | None = None,
    ) -> VerificationResult:
        """규칙 검사와 모델 검토를 합친 검증 결과를 돌려준다.

        ``trace``를 넘기면 스키마 변환과 실행 상태를 ``TraceEvent``로 추가한다.
        상품 원문과 모델 응답 원문은 trace에 저장하지 않는다.

        raises VerificationError: 모델이 없거나, 호출이 실패했거나, 검토 범위가 맞지 않는 경우.
        """
        self._append_trace(
            trace,
            action="verification_started",
            status="started",
            detail=f"DraftAssessment 입력: findings={len(draft.findings)}",
        )
        # 모델 호출 전에 확정적으로 검사할 수 있는 규칙 결과를 먼저 만든다.
        # 이후 모델 단계가 실패해도 이 결과는 VerificationError에 보존된다.
        rules = self.verify_rules(draft, trace=trace)
        if self._structured is None:
            self._append_trace(
                trace,
                action="verification_failed",
                status="failed",
                detail="모델이 없어 전체 검증을 실행하지 못했습니다.",
            )
            raise VerificationError(
                "모델이 없습니다. VerificationAgent.from_env()를 쓰거나, "
                "API 없이 구조만 볼 때는 verify_rules()를 호출하세요.",
                partial_result=rules,
            )
        self._append_trace(
            trace,
            action="model_review_started",
            status="started",
            detail="DraftAssessment를 GPT 구조화 출력 _Review로 검토합니다.",
        )
        review = self._review_with_trace(
            self._build_messages(draft),
            subject_id=draft.product.product_id,
            rules=rules,
            trace=trace,
        )

        self._append_trace(
            trace,
            action="model_review_completed",
            status="completed",
            detail=(
                f"_Review 생성: issues={len(review.issues)}, "
                f"checked_finding_ids={len(review.checked_finding_ids)}"
            ),
        )
        try:
            self._check_scope(review, draft)
            self._append_trace(
                trace,
                action="scope_validated",
                status="completed",
                detail=f"_Review 검토 범위 확인: findings={len(draft.findings)}",
            )
            result = self._merge(rules, review)
        except VerificationError as exc:
            self._append_trace(
                trace,
                action="review_validation_failed",
                status="failed",
                detail="_Review의 ID 참조 또는 검토 범위가 유효하지 않습니다.",
            )
            raise VerificationError(
                str(exc),
                partial_result=rules,
            ) from exc
        except Exception as exc:
            self._append_trace(
                trace,
                action="result_merge_failed",
                status="failed",
                detail=f"VerificationResult 생성 실패: {type(exc).__name__}",
            )
            raise VerificationError(
                f"모델 검토 결과 처리에 실패했습니다: {type(exc).__name__}",
                partial_result=rules,
            ) from exc

        self._append_trace(
            trace,
            action="result_merged",
            status="completed",
            detail=(
                "규칙 VerificationResult와 _Review를 최종 VerificationResult로 병합: "
                f"status={result.status.value}, issues={len(result.issues)}"
            ),
        )
        self._append_trace(
            trace,
            action="verification_completed",
            status="completed",
            detail=f"VerificationResult 반환: status={result.status.value}",
        )
        return result

    @staticmethod
    def _append_trace(
        trace: list[TraceEvent] | None,
        *,
        action: str,
        status: str,
        detail: str,
    ) -> None:
        """선택적으로 실행 이력을 추가한다. 내부 추론이나 원문 데이터는 기록하지 않는다."""
        if trace is None:
            return
        sequence = trace[-1].sequence + 1 if trace else 1
        trace.append(
            TraceEvent(
                sequence=sequence,
                stage="verification",
                component="VerificationAgent",
                action=action,
                status=status,
                detail=detail,
            )
        )

    def verify_rules(
        self,
        draft: DraftAssessment,
        *,
        trace: list[TraceEvent] | None = None,
    ) -> VerificationResult:
        """구조·근거 유무만 검사한다. API를 호출하지 않는다.

        의미 검증이나 법적 승인을 대신하지 않으므로 이 결과만으로 검증 완료로 쓰면 안 된다.
        """
        self._append_trace(
            trace,
            action="rules_started",
            status="started",
            detail="DraftAssessment 구조와 근거 규칙 검사를 시작합니다.",
        )
        context = run_rule_checks(draft)

        result = VerificationResult(
            status=Status.APPROVED,
            issues=context.issues,
            additional_tools_required=context.additional_tools,
            # 초안에 이미 있는 사용자 질문도 상태 판단에 함께 반영한다.
            follow_up_questions=list(draft.follow_up_questions),
        )
        result.status = self._status(result)
        result.review_summary = (
            "규칙 검사만 실행했습니다. 모델 의미 검증과 외부 법령 조회는 수행하지 않았습니다."
        )
        # checked_finding_ids는 의미 검토를 마친 모델 결과에서만 채운다.
        self._append_trace(
            trace,
            action="rules_completed",
            status="completed",
            detail=(
                "DraftAssessment -> 규칙 VerificationResult: "
                f"status={result.status.value}, issues={len(result.issues)}"
            ),
        )
        return result

    def _build_messages(self, draft: DraftAssessment) -> list[dict[str, str]]:
        payload = draft.model_dump(mode="json")
        # 조회 파라미터와 원시 응답에는 키·토큰·개인정보가 섞일 수 있어 모델에 보내지 않는다.
        # tool_results[].findings는 최상위 findings와 항상 같아야 한다는 규칙을 verify_rules()가 이미 검사하므로, 모델에는 최상위 목록 한 벌만 보내 입력 토큰을 줄인다.
        for tool_record in payload["tool_results"]:
            for key in ("query", "raw_response", "error", "findings"):
                tool_record.pop(key, None)
        # 출력 JSON Schema는 with_structured_output이 API에 직접 전달한다.
        # 프롬프트에 다시 붙이면 토큰만 늘고 두 스키마가 어긋날 수 있어 넣지 않는다.
        return [
            {"role": "system", "content": self.prompt.text},
            {"role": "user", "content": json.dumps({"draft": payload}, ensure_ascii=False)},
        ]

    @staticmethod
    def _check_scope(review: _Review, draft: DraftAssessment) -> None:
        """모델이 모든 판단을 한 번씩 검토했는지, 없는 ID를 만들지 않았는지 확인한다."""
        expected = {f.finding_id for f in draft.findings}
        checked = review.checked_finding_ids
        if len(checked) != len(set(checked)):
            raise VerificationError("checked_finding_ids에 중복이 있습니다.")
        if set(checked) != expected:
            missing = sorted(expected - set(checked))
            unknown = sorted(set(checked) - expected)
            raise VerificationError(
                f"검토 범위가 입력과 다릅니다. 누락 {missing}, 존재하지 않는 ID {unknown}"
            )
        for issue in review.issues:
            unknown = sorted(set(issue.related_finding_ids) - expected)
            if unknown:
                raise VerificationError(f"지적이 존재하지 않는 판단 ID를 참조합니다: {unknown}")

    @staticmethod
    def _unique_issues(issues: list[VerificationIssue]) -> list[VerificationIssue]:
        unique: list[VerificationIssue] = []
        seen: set[tuple] = set()

        for issue in issues:
            key = (
                issue.severity,
                issue.issue_type,
                issue.description,
                tuple(sorted(issue.related_finding_ids)),
                issue.recommended_action,
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(issue)

        return unique

    def _merge(self, rules: VerificationResult, review: _Review) -> VerificationResult:
        """규칙 검사 결과를 모델 검토 위에 덧붙인다. 코드가 찾은 문제는 모델이 지울 수 없다."""
        merged_issues = rules.issues + [VerificationIssue(**i.model_dump()) for i in review.issues]
        issues = self._unique_issues(merged_issues)
        tools = list(
            dict.fromkeys(rules.additional_tools_required + review.additional_tools_required)
        )
        # 같은 질문이 규칙과 모델에서 겹치면 required가 강한 쪽을 남긴다.
        questions: dict[str, FollowUpQuestion] = {q.question: q for q in rules.follow_up_questions}
        for question in review.follow_up_questions:
            existing = questions.get(question.question)
            if existing is None:
                questions[question.question] = FollowUpQuestion(**question.model_dump())
            elif question.required and not existing.required:
                questions[question.question] = existing.model_copy(update={"required": True})

        merged = VerificationResult(
            status=Status.APPROVED,
            issues=issues,
            additional_tools_required=tools,
            follow_up_questions=list(questions.values()),
            checked_finding_ids=list(review.checked_finding_ids),
        )
        # 최종 상태와 요약은 병합된 실제 결과를 기준으로 코드가 만든다.
        # 모델 요약을 그대로 쓰면 규칙이 찾은 추가 도구와 모순될 수 있다.
        merged.status = self._status(merged)
        summary_parts = [f"검증 상태 {merged.status.value}, 지적 {len(issues)}건."]
        if tools:
            names = ", ".join(tool.value for tool in tools)
            summary_parts.append(f"추가 검토 도구: {names}.")
        required_questions = sum(question.required for question in merged.follow_up_questions)
        if required_questions:
            summary_parts.append(f"필수 확인 질문: {required_questions}건.")
        if not issues and not tools and not merged.follow_up_questions:
            summary_parts.append("제공된 자료 범위에서 추가 문제를 찾지 못했습니다.")
        summary_parts.append("외부 법령 조회와 현행성 확인은 수행하지 않았습니다.")
        merged.review_summary = " ".join(summary_parts)
        merged.verified_at = utc_now()
        return merged

    @staticmethod
    def _status(result: VerificationResult) -> Status:
        """검증 결과에서 가장 우선하는 후속 상태를 고른다.

        Tool 재실행으로 해결할 수 없는 critical 이슈는 초안 수정을 우선한다.
        필수 질문은 사람이 제공해야 하는 정보이므로 Tool 재실행보다 앞선다.
        """

        blocking_critical = any(
            issue.severity == "critical"
            and issue.issue_type not in _TOOL_RECOVERABLE_ISSUES
            for issue in result.issues
        )
        if blocking_critical:
            return Status.REVISION_REQUIRED

        if any(question.required for question in result.follow_up_questions):
            return Status.USER_INPUT_REQUIRED

        if result.additional_tools_required:
            return Status.TOOLS_REQUIRED

        # 복구 가능한 critical이라도 실행할 Tool이 지정되지 않았다면 자동 복구가 불가능.
        if any(issue.severity == "critical" for issue in result.issues):
            return Status.REVISION_REQUIRED

        if result.issues or result.follow_up_questions:
            return Status.APPROVED_WITH_WARNINGS

        return Status.APPROVED
