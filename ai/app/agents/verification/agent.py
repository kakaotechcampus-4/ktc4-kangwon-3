"""규칙 검사와 모델 검토를 합쳐 심사 초안을 검증한다. Tool 재실행·재시도 제한은 파이프라인 몫."""

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
from ..base import AgentError, AgentResult, AgentRunMeta, BaseAgent, ModelFailurePhase
from .rules import run_rule_checks
from .schemas import _Review

_TOOL_RECOVERABLE_ISSUES = frozenset(
    {
        IssueType.TOOL_FAILURE,
        IssueType.MISSING_EVIDENCE,
    }
)


class VerificationError(AgentError):
    """모델 검증 미완료. ``partial_result``는 규칙 검사 결과(VerificationResult).

    파이프라인은 이를 ``FinalVerificationStatus.INCOMPLETE``로 처리하고 검증 완료로 보지 않아야 함.
    """


class VerificationAgent(BaseAgent[DraftAssessment, _Review, VerificationResult]):
    """심사 초안의 근거·누락·모순을 검증한다. 흐름(규칙 → 모델 검토 → 병합)이 달라 ``run_with_meta``를 다시 정의.

    모델을 자동으로 만들지 않음(``from_env``로 생성). 모델 없이도 ``verify_rules``는 동작하고 ``run``은 실패.
    """

    component_name = "verification"
    prompt_name = PromptName.VERIFICATION
    output_schema = _Review
    error_class = VerificationError
    task_name = "모델 검토"
    structured_output_options = {"method": "json_schema", "strict": True}
    creates_default_model = False

    @classmethod
    def from_env(cls) -> "VerificationAgent":
        """설정의 모델 프로필로 모델을 만들어 에이전트를 만든다.

        Returns:
            VerificationAgent: 모델이 있는 에이전트.

        Raises:
            ConfigError: 모델 설정이 없거나 잘못된 경우.
        """
        from ...config import build_agent_model

        return cls(build_agent_model(cls.component_name))

    def _review_with_trace(
        self,
        messages: list[dict[str, str]],
        *,
        subject_id: str,
        rules: VerificationResult,
        trace: list[TraceEvent] | None,
    ) -> tuple[_Review, AgentRunMeta]:
        """모델 검토를 호출한다. 실패하면 trace를 남기고 같은 예외를 다시 던짐 (#171 §4.2).

        Args:
            messages: 모델에 보낼 메시지.
            subject_id: 사용량 기록 대상 상품 ID.
            rules: 규칙 검사 결과. 실패 시 예외의 partial_result로 보존.
            trace: 실행 이력. None이면 기록 안 함.

        Returns:
            tuple[_Review, AgentRunMeta]: 모델 검토 결과와 실행 정보.

        Raises:
            VerificationError: 호출·파싱 실패. 원인은 ``__cause__``.
        """
        try:
            return self._invoke_with_meta(messages, subject_id=subject_id, partial_result=rules)
        except VerificationError as exc:
            # 모델 호출·파싱 실패 → trace만 남기고 같은 예외를 그대로 다시 던짐 (원인은 __cause__ 유지)
            cause = exc.__cause__
            self._append_trace(
                trace,
                action="model_review_failed",
                status="failed",
                detail=f"_Review 생성 실패: {type(cause).__name__}",
            )
            raise

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """검토 실패 문구를 만든다. 호출·파싱 구분 없이 같은 문구 (구분은 error_type·``__cause__``).

        응답 본문이 섞일 수 있어 외부에 그대로 공유하지 않음.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        return f"모델 검토 호출에 실패했습니다: {type(cause).__name__}: {cause}"

    def run(self, input: DraftAssessment, *, trace: list[TraceEvent] | None = None) -> VerificationResult:
        """규칙 검사와 모델 검토를 합친 검증 결과를 돌려준다.

        Args:
            input: 검증할 심사 초안.
            trace: 실행 이력. 넘기면 단계별 TraceEvent를 추가 (상품·응답 원문은 기록 안 함).

        Returns:
            VerificationResult: 병합된 검증 결과.

        Raises:
            VerificationError: 모델이 없거나, 호출·파싱이 실패했거나, 검토 범위가 맞지 않는 경우.
                partial_result는 규칙 검사 결과.
        """
        return self.run_with_meta(input, trace=trace).result

    def run_with_meta(
        self,
        input: DraftAssessment,
        *,
        trace: list[TraceEvent] | None = None,
    ) -> AgentResult[VerificationResult]:
        """규칙 검사와 모델 검토를 합친 검증 결과와 모델 검토 호출의 실행 정보를 돌려준다.

        Args:
            input: 검증할 심사 초안.
            trace: 실행 이력. 넘기면 단계별 TraceEvent를 추가 (상품·응답 원문은 기록 안 함).

        Returns:
            AgentResult[VerificationResult]: 병합된 검증 결과와 실행 정보.

        Raises:
            VerificationError: 모델이 없거나, 호출·파싱이 실패했거나, 검토 범위가 맞지 않는 경우.
                partial_result는 규칙 검사 결과, 모델 호출 뒤 실패면 meta도 담음.
        """
        draft = input
        self._append_trace(
            trace,
            action="verification_started",
            status="started",
            detail=f"DraftAssessment 입력: findings={len(draft.findings)}",
        )
        rules = self.verify_rules(draft, trace=trace)
        # 모델 미주입 (from_env 없이 생성) → 규칙 결과를 담아 실패
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
        review, meta = self._review_with_trace(
            self._build_messages(draft),
            subject_id=self._subject_id(draft),
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
            # _check_scope 실패 (검토 ID 중복·누락·없는 ID 참조)
            self._append_trace(
                trace,
                action="review_validation_failed",
                status="failed",
                detail="_Review의 ID 참조 또는 검토 범위가 유효하지 않습니다.",
            )
            raise VerificationError(
                str(exc),
                partial_result=rules,
                meta=meta,
            ) from exc
        except Exception as exc:
            # 모델 출력을 VerificationResult로 병합하다 실패 (예상 밖 값 등)
            self._append_trace(
                trace,
                action="result_merge_failed",
                status="failed",
                detail=f"VerificationResult 생성 실패: {type(exc).__name__}",
            )
            raise VerificationError(
                f"모델 검토 결과 처리에 실패했습니다: {type(exc).__name__}",
                partial_result=rules,
                meta=meta,
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
        return AgentResult(result, meta)

    def _subject_id(self, input: DraftAssessment) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 심사 초안.

        Returns:
            str: 상품 ID.
        """
        return input.product.product_id

    @staticmethod
    def _append_trace(
        trace: list[TraceEvent] | None,
        *,
        action: str,
        status: str,
        detail: str,
    ) -> None:
        """실행 이력에 TraceEvent 하나를 추가한다. 추론·원문은 기록 안 함.

        Args:
            trace: 실행 이력. None이면 아무것도 안 함.
            action: 단계 이름.
            status: started·completed·failed.
            detail: 짧은 설명.
        """
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
        """모델 없이 구조·근거 유무만 검사한다. 의미 검증이 아니라 이 결과만으로 검증 완료로 쓰지 않음.

        Args:
            draft: 검증할 심사 초안.
            trace: 실행 이력. None이면 기록 안 함.

        Returns:
            VerificationResult: 규칙 검사 결과.
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
            follow_up_questions=list(draft.follow_up_questions),
        )
        result.status = self._status(result)
        result.review_summary = (
            "규칙 검사만 실행했습니다. 모델 의미 검증과 외부 법령 조회는 수행하지 않았습니다."
        )
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
        """심사 초안을 모델 메시지로 만든다.

        조회 파라미터·원시 응답(키·개인정보가 섞일 수 있음)과 Tool별 findings(최상위와 같음)는 뺌.
        출력 스키마는 API로 전달되므로 프롬프트에 넣지 않음.

        Args:
            draft: 검증할 심사 초안.

        Returns:
            list[dict[str, str]]: [시스템 프롬프트, 초안 JSON].
        """
        payload = draft.model_dump(mode="json")
        for tool_record in payload["tool_results"]:
            for key in ("query", "raw_response", "error", "findings"):
                tool_record.pop(key, None)
        return [
            {"role": "system", "content": self.prompt.text},
            {"role": "user", "content": json.dumps({"draft": payload}, ensure_ascii=False)},
        ]

    @staticmethod
    def _check_scope(review: _Review, draft: DraftAssessment) -> None:
        """모델이 모든 판단을 한 번씩 검토했고 없는 ID를 만들지 않았는지 확인한다.

        Args:
            review: 모델 검토 결과.
            draft: 검증한 심사 초안.

        Raises:
            VerificationError: 검토 ID 중복·누락·없는 ID 참조.
        """
        expected = {f.finding_id for f in draft.findings}
        checked = review.checked_finding_ids
        # 같은 판단을 두 번 이상 검토했다고 보고
        if len(checked) != len(set(checked)):
            raise VerificationError("checked_finding_ids에 중복이 있습니다.")
        # 검토한 ID 집합이 입력 판단과 다름 (빠뜨렸거나 없는 ID를 만듦)
        if set(checked) != expected:
            missing = sorted(expected - set(checked))
            unknown = sorted(set(checked) - expected)
            raise VerificationError(
                f"검토 범위가 입력과 다릅니다. 누락 {missing}, 존재하지 않는 ID {unknown}"
            )
        for issue in review.issues:
            unknown = sorted(set(issue.related_finding_ids) - expected)
            # 지적이 입력에 없는 판단 ID를 참조
            if unknown:
                raise VerificationError(f"지적이 존재하지 않는 판단 ID를 참조합니다: {unknown}")

    @staticmethod
    def _unique_issues(issues: list[VerificationIssue]) -> list[VerificationIssue]:
        """내용이 같은 이슈를 처음 것만 남긴다 (issue_id 제외).

        Args:
            issues: 이슈 목록.

        Returns:
            list[VerificationIssue]: 중복을 뺀 목록. 순서 유지.
        """
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
        """규칙 검사 결과와 모델 검토를 합친다. 규칙이 찾은 문제는 모델이 지울 수 없음.

        Args:
            rules: 규칙 검사 결과.
            review: 모델 검토 결과.

        Returns:
            VerificationResult: 병합 결과. 상태·요약은 코드가 계산.
        """
        merged_issues = rules.issues + [VerificationIssue(**i.model_dump()) for i in review.issues]
        issues = self._unique_issues(merged_issues)
        tools = list(
            dict.fromkeys(rules.additional_tools_required + review.additional_tools_required)
        )
        questions: dict[str, FollowUpQuestion] = {q.question: q for q in rules.follow_up_questions}
        for question in review.follow_up_questions:
            existing = questions.get(question.question)
            if existing is None:
                questions[question.question] = FollowUpQuestion(**question.model_dump())
            # 규칙·모델에 같은 질문 → 한쪽이라도 필수면 필수로
            elif question.required and not existing.required:
                questions[question.question] = existing.model_copy(update={"required": True})

        merged = VerificationResult(
            status=Status.APPROVED,
            issues=issues,
            additional_tools_required=tools,
            follow_up_questions=list(questions.values()),
            checked_finding_ids=list(review.checked_finding_ids),
        )
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
        """검증 결과의 후속 상태를 고른다.

        우선순위: Tool로 못 고치는 critical → 수정, 필수 질문 → 사용자 입력, 추가 Tool → 재실행.

        Args:
            result: 검증 결과.

        Returns:
            Status: 후속 상태.
        """
        blocking_critical = any(
            issue.severity == "critical"
            and issue.issue_type not in _TOOL_RECOVERABLE_ISSUES
            for issue in result.issues
        )
        # Tool 재실행으로 못 고치는 critical
        if blocking_critical:
            return Status.REVISION_REQUIRED

        if any(question.required for question in result.follow_up_questions):
            return Status.USER_INPUT_REQUIRED

        if result.additional_tools_required:
            return Status.TOOLS_REQUIRED

        # Tool로 고칠 수 있는 critical인데 재실행할 Tool이 지정되지 않음
        if any(issue.severity == "critical" for issue in result.issues):
            return Status.REVISION_REQUIRED

        if result.issues or result.follow_up_questions:
            return Status.APPROVED_WITH_WARNINGS

        return Status.APPROVED
