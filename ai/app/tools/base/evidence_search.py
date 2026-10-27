"""근거 조회형 Tool 5개의 공통 흐름. 앞(조건 추출)·뒤(결과 조립)는 고정, 가운데(_judge)만 Tool별."""

from abc import abstractmethod
from collections.abc import Callable, Iterable
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel

from ...schemas.agent import ToolSelectionItem
from ...schemas.product import Product
from ...schemas.schemas import Determination, LegalSource, RegulatoryFinding, RiskLevel, ToolResult, ToolStatus
from ..common.facts import group_facts, product_snippets, quote_matches
from ..common.law import EvidenceUnavailable
from .errors import ToolModelError
from .run import ToolRun
from .steps import ToolStep, ToolStepInput
from .tool import RegulatoryTool

_T = TypeVar("_T")
_Item = TypeVar("_Item")

NO_SNIPPETS = "입력에 인용 가능한 상품 설명이 없습니다."
SCOPE_NOTE = "전체 상품 원문이 아니라 전달된 설명·속성 근거만 확인했습니다."
SELECTIONS_LIMIT = 3


class EvidenceSearchTool(RegulatoryTool):
    """근거 조회형 Tool 5개의 공통 흐름. 모델은 확정 판단을 내지 않음.

    흐름: 원문 조각 → (없으면 정보 부족) → _prepare → 조건 추출(_extract) → _judge → 결과 조립(_result).
    하위 클래스는 ClassVar와 _judge·_detail을 정하고, 필요한 훅만 다시 정의.
    생성 시 설정·모델·API 연결을 만들지 않음 (레지스트리 생성 계약).

    Attributes:
        facts_step: 조건 추출 단계 클래스.
        review_step: 후보 선택 단계 클래스.
        error_class: 조회 실패 때 던질 예외. ToolModelError 하위.
        field_labels: 조건 필드 → 표시 이름.
        questions: 재질문 문구. 없는 필드는 "{표시 이름} 정보가 필요합니다."
        empty_fields: 인용할 원문이 없을 때 물을 필드.
        base_assumptions: 조건 추출 전부터 넣는 가정 (원문 범위 안내 다음).
        conflict_note: 추출 단계 모순 가정의 끝 문장.
        insufficient: 기본 정보 부족 판단의 (제목, 요약, 근거).
        tracks_conflicts: query에 "conflicted" 목록을 처음부터 둘지.
        hints_with_attributes: 모델 힌트에 속성 이름·값을 넣을지.
        run_class: 실행 상태 클래스. Tool별 값이 더 필요하면 ToolRun 하위 클래스.
    """

    facts_step: ClassVar[type[ToolStep]]
    review_step: ClassVar[type[ToolStep]]
    error_class: ClassVar[type[ToolModelError]]
    field_labels: ClassVar[dict[str, str]]
    questions: ClassVar[dict[str, str]] = {}
    empty_fields: ClassVar[tuple[str, ...]] = ()
    base_assumptions: ClassVar[tuple[str, ...]] = ()
    conflict_note: ClassVar[str]
    insufficient: ClassVar[tuple[str, str, str]]
    tracks_conflicts: ClassVar[bool] = False
    hints_with_attributes: ClassVar[bool] = False
    run_class: ClassVar[type[ToolRun]] = ToolRun

    def __init__(self, model=None, *, configured_model: str | None = None, top_k: int = 8):
        """모델과 후보 수를 받는다. 모델은 실행할 때 만든다.

        Args:
            model: 구조화 출력을 지원하는 채팅 모델. None이면 실행할 때 Tool 프로필(TOOL_PROFILES)로 만듦.
            configured_model: 사용량 기록용 모델 이름.
            top_k: 선택 모델에 넘길 후보 수.

        Raises:
            ValueError: top_k가 양의 정수가 아닌 경우.
        """
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k는 양의 정수여야 합니다.")
        self._model = model
        self._configured_model = configured_model
        self._top_k = top_k
        self._steps: tuple[ToolStep, ToolStep] | None = None

    def _get_steps(self) -> tuple[ToolStep, ToolStep]:
        """조건 추출·선택 단계를 처음 쓸 때 만든다. 두 단계가 모델 하나를 같이 씀.

        Returns:
            tuple[ToolStep, ToolStep]: (조건 추출 단계, 선택 단계).
        """
        if self._steps is None:
            if self._model is None:
                # 모델 프로필(#311)의 Tool 표(TOOL_PROFILES)에서 이 Tool의 모델을 고름
                from ...config import build_tool_model
                self._model = build_tool_model(self.tool_name)
            options = {"configured_model": self._configured_model}
            self._steps = (self.facts_step(self._model, **options), self.review_step(self._model, **options))
        return self._steps

    # -- 흐름 --

    def _run(self, product: Product, decision: ToolSelectionItem) -> ToolResult:
        """앞(조건 추출)·뒤(결과 조립)는 고정하고 가운데는 _judge에 맡긴다.

        Args:
            product: 추출 에이전트가 만든 상품 정보.
            decision: 이 툴의 선택 결정 (selected=True).

        Returns:
            ToolResult: 심사 결과.
        """
        run = self.run_class(product, decision, snippets=product_snippets(product))
        if self.tracks_conflicts:
            run.query["conflicted"] = run.conflicted
        if not run.snippets:
            run.missing = list(self.empty_fields)
            run.assumptions = [NO_SNIPPETS]
            return self._result(run, [])
        run.assumptions = [SCOPE_NOTE, *self.base_assumptions]
        self._prepare(run)
        self._extract(run)
        return self._result(run, self._judge(run))

    def _prepare(self, run: ToolRun) -> None:
        """조건 추출 전 준비 (품목 목록·근거 조회 등). 기본은 없음.

        Args:
            run: 실행 상태.
        """

    def _extract(self, run: ToolRun) -> None:
        """조건 추출 → 원문 대조 → 필드별 묶기 → 공통 가정. 원문과 대조되지 않는 조건은 그 항목만 버림.

        가정 순서: 버린 조건 → _read_facts가 남긴 가정 → 추출 단계 모순.

        Args:
            run: 실행 상태. extracted·facts·by_field·assumptions·query를 채움.
        """
        facts_step, _ = self._get_steps()
        run.extracted = facts_step.run(ToolStepInput(self._facts_payload(run), run.product.product_id))
        raw = self._raw_facts(run)
        run.facts = [fact for fact in raw if self._fact_matches(fact, run)]
        run.query["dropped_facts"] = len(raw) - len(run.facts)
        run.by_field = group_facts(run.facts)
        if run.query["dropped_facts"]:
            run.assumptions.append(f"원문과 대조되지 않은 상품 조건 {run.query['dropped_facts']}개를 제외했습니다.")
        self._read_facts(run)
        if run.product.conflicts:
            # 추출 단계가 표시한 모순이 조회 전체를 막지 않게 가정으로만 남김
            run.assumptions.append("추출 단계가 상품 정보의 모순을 표시했습니다: " + "; ".join(run.product.conflicts)
                                   + self.conflict_note)

    def _facts_payload(self, run: ToolRun) -> dict[str, Any]:
        """조건 추출 모델 입력. 기본은 힌트와 인용할 원문 조각.

        Args:
            run: 실행 상태.

        Returns:
            dict[str, Any]: 모델에 JSON으로 보낼 값.
        """
        return {"hints": self._hints(run.product), "evidence": run.snippets}

    def _hints(self, product: Product) -> dict[str, Any]:
        """조건 추출 모델에 주는 참고값. 판단 근거가 아니며 인용은 evidence에서만 함.

        원문(listing_text)은 evidence에 이미 있어 뺌. hints_with_attributes면 속성 이름·값을 넣음.

        Args:
            product: 상품 정보.

        Returns:
            dict[str, Any]: 참고값.
        """
        hints = product.model_dump(mode="json", exclude={"listing_text", "attributes", "source_url"},
                                   exclude_none=True)
        if self.hints_with_attributes and product.attributes:
            hints["attributes"] = [{"name": attr.name, "value": attr.value} for attr in product.attributes]
        return hints

    def _raw_facts(self, run: ToolRun) -> list:
        """원문 대조 전 조건 목록. 기본은 추출 출력의 facts.

        Args:
            run: 실행 상태 (extracted 채워짐).

        Returns:
            list: 대조할 조건.
        """
        return list(run.extracted.facts)

    def _fact_matches(self, fact, run: ToolRun) -> bool:
        """조건의 인용이 원문 조각 안에 있고 값이 인용 안에 있는지.

        Args:
            fact: 조건 하나.
            run: 실행 상태.

        Returns:
            bool: 남길 조건이면 True.
        """
        return quote_matches(fact, run.snippets)

    def _read_facts(self, run: ToolRun) -> None:
        """대조된 조건을 읽어 Tool별 상태·가정을 남긴다 (주파수·연령·충돌 등). 기본은 없음.

        Args:
            run: 실행 상태.
        """

    @abstractmethod
    def _judge(self, run: ToolRun) -> list[RegulatoryFinding]:
        """Tool별 가운데: 조회·규칙·선택으로 판단을 만든다.

        Args:
            run: 실행 상태. missing·assumptions·actions·query를 함께 채움.

        Returns:
            list[RegulatoryFinding]: 판단. 비면 결과 조립 때 정보 부족 판단 하나를 넣음.
        """

    @abstractmethod
    def _detail(self, run: ToolRun, findings: list[RegulatoryFinding]) -> BaseModel:
        """Tool별 상세 결과(ToolResult.result).

        Args:
            run: 실행 상태.
            findings: 최종 판단 (기본 판단 포함).

        Returns:
            BaseModel: Tool별 Assessment.
        """

    # -- 공통 부품 --

    def _lookup(self, run: ToolRun, call: Callable[[], _T], *, failure: str,
                unavailable: str | None = None) -> _T | None:
        """조회 하나를 실행한다. 근거를 확인할 수 없으면 가정을 남기고 None.

        Args:
            run: 실행 상태.
            call: 조회 함수.
            failure: 조회 실패 때 예외 문구.
            unavailable: EvidenceUnavailable 때 남길 가정. None이면 남기지 않음.

        Returns:
            _T | None: 조회 결과. 근거를 확인할 수 없으면 None.

        Raises:
            ToolModelError: 조회 실패 (실제 타입은 error_class). 원인은 예외 체인에 보존.
        """
        try:
            return call()
        except EvidenceUnavailable:
            if unavailable is not None:
                run.assumptions.append(unavailable)
            return None
        except Exception as exc:
            raise self.error_class(failure) from exc

    def _pick(self, run: ToolRun, selections: Iterable, candidates: dict[str, _Item], *, key: str = "item_id",
              limit: int | None = SELECTIONS_LIMIT,
              skip: Callable[[_Item], bool] | None = None) -> list[tuple[_Item, Any, list[str]]]:
        """선택 모델 결과를 후보·원문과 대조해 쓸 선택만 남긴다.

        해당 없음·후보에 없음·중복·확인된 조건 없음을 거른 뒤 상한을 적용 (앞쪽 무효 선택이 맞는 후보를 밀어내지 않게).
        query에 not_applicable·dropped_candidates·over_limit를 셈.

        Args:
            run: 실행 상태.
            selections: 선택 모델의 선택 목록.
            candidates: 후보 ID → 후보.
            key: 선택에서 후보 ID를 담은 필드 이름.
            limit: 남길 최대 수. None이면 제한 없음.
            skip: 코드 규칙으로 버릴 후보 (dropped_candidates로 셈).

        Returns:
            list[tuple[_Item, Any, list[str]]]: (후보, 선택, 확인된 근거 필드) 목록.
        """
        chosen: list[tuple[_Item, Any, list[str]]] = []
        chosen_ids: set[str] = set()
        for selection in selections:
            if not selection.applies:
                run.query["not_applicable"] += 1
                continue
            item_id = getattr(selection, key)
            item = candidates.get(item_id)
            # 확인되지 않은 조건을 근거로 든 부분은 무시하고, 확인된 조건이 하나도 없을 때만 선택을 버림
            used = [field for field in dict.fromkeys(selection.fact_fields) if field in run.by_field]
            if item is None or item_id in chosen_ids or not used or (skip is not None and skip(item)):
                run.query["dropped_candidates"] += 1
                continue
            if limit is not None and len(chosen) >= limit:
                run.query["over_limit"] = run.query.get("over_limit", 0) + 1
                continue
            chosen.append((item, selection, used))
            chosen_ids.add(item_id)
        return chosen

    def _fact_line(self, fact) -> str:
        """판단에 남길 조건 문구.

        Args:
            fact: 조건 하나.

        Returns:
            str: "{표시 이름}: {값} (근거: {인용})".
        """
        return f"{self.field_labels[fact.field]}: {fact.value} (근거: {fact.quote})"

    def _finding(self, *, subject: str, summary: str, rationale: str, determination: Determination,
                 risk: RiskLevel, facts: list, assumptions: list[str], sources: list[LegalSource],
                 requirements: list[str] | None = None) -> RegulatoryFinding:
        """판단 하나를 만든다. 가정은 지금 시점의 목록을 복사.

        Args:
            subject: 제목.
            summary: 요약.
            rationale: 근거 설명.
            determination: 판정.
            risk: 위험도.
            facts: 판단에 쓴 조건.
            assumptions: 가정.
            sources: 근거 조문.
            requirements: 이 판단의 할 일.

        Returns:
            RegulatoryFinding: 판단.
        """
        return RegulatoryFinding(
            tool_name=self.tool_name, subject=subject, determination=determination, risk_level=risk,
            summary=summary, rationale=rationale, legal_sources=sources, requirements=list(requirements or []),
            product_facts_used=[self._fact_line(fact) for fact in facts], assumptions=list(assumptions),
        )

    def _question(self, run: ToolRun, field: str) -> str:
        """재질문 문구. 값이 서로 달라 판단하지 않은 필드는 확인 요청 문구.

        Args:
            run: 실행 상태.
            field: 조건 필드.

        Returns:
            str: 재질문 문구.
        """
        label = self.field_labels[field]
        if field in run.conflicted:
            return f"{label} 정보가 서로 달라 확인이 필요합니다."
        return self.questions.get(field, f"{label} 정보가 필요합니다.")

    def _result(self, run: ToolRun, findings: list[RegulatoryFinding]) -> ToolResult:
        """결과를 조립한다. 판단이 비면 정보 부족 판단 하나를 넣음 (빈 후보를 비대상 근거로 쓰지 않음).

        Args:
            run: 실행 상태.
            findings: _judge가 만든 판단.

        Returns:
            ToolResult: 심사 결과.
        """
        run.missing = list(dict.fromkeys(run.missing))
        if not findings:
            subject, summary, rationale = self.insufficient
            findings = [self._finding(
                subject=subject, summary=summary, rationale=rationale,
                determination=Determination.INSUFFICIENT_INFORMATION, risk=RiskLevel.UNKNOWN,
                facts=run.facts, assumptions=run.assumptions, sources=[],
            )]
        return ToolResult(
            tool_name=self.tool_name, selected=True, selection_reason=run.decision.reason,
            status=ToolStatus.SUCCESS, result=self._detail(run, findings), findings=findings,
            required_actions=list(dict.fromkeys(run.actions)),
            missing_information=[self._question(run, field) for field in run.missing],
            query=run.query,
        )
