"""어린이제품 안전관리 근거: 법 제2조(정의), 시행규칙 별표 1~3(제도별 품목), 운용요령 별표 3~5(적용범위).

법제처 별표는 글자로 그린 표라 칸 구조가 불안정하다. 이 모듈이 법제처 응답을 직접 읽어 행을 만든다.
- 시행규칙 별표 1~3: 2칸 표(품목 | 적용 안전기준)라 코드로 행을 나눈다.
- 운용요령 별표 3~5: 적용범위가 긴 설명문이라 칸을 더 나누지 않고 품목 단위 원문 덩어리로 붙인다.
  연령·제외 조건은 품목 선택 단계 모델이 원문을 읽는다.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ..common.law import (
    DocRef, EvidenceUnavailable, LawLookup, annex_text, compact, join_wrapped, load_admrul, load_law,
    normalize_text,
)
from ..common.ranking import bigrams

LAW_NAME = "어린이제품 안전 특별법"
LAW_ID = "012070"
RULE_NAME = "어린이제품 안전 특별법 시행규칙"
RULE_ID = "012304"
NOTICE_NAME = "어린이제품안전관리제도 운용요령"
NOTICE_ID = "2087627"

_KOREAN_LABELS = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"
_LABEL_RE = re.compile(r"^\s*(\d{1,2}|[가-힣])\s*\.\s*(.*)$")
_STANDARD_RE = re.compile(r"^\s*(\d{1,2}\)|[가-힣]\s*\.)\s*(.*)$")
_DELETED_RE = re.compile(r"^삭제\s*<")
_COMMON_STANDARD_RE = re.compile(r"2\.\s*개별\s*안전기준이\s*없는.*?적용한다\.")
_LINK_THRESHOLD = 0.4
_SCOPE_LIMIT = 1500
# 조회 순위 밖에서 함께 넘기는 안전인증·안전확인 품목의 적용범위 길이. 품목을 알아볼 만큼만 넣어 입력을 줄인다.
SHORT_SCOPE_LIMIT = 300
# 품목명에 붙은 포함 문구. 예: "어린이용 안경테(선글라스를 포함한다)", "어린이용 온열팩 (주머니난로 포함)".
_INCLUDES_RE = re.compile(r"\s*\(([^()]*포함[^()]*)\)")

logger = logging.getLogger(__name__)


def without_includes(name: str) -> str:
    """품목명에서 포함 문구를 뗀 이름. 조회어·순위에 "포함한다" 같은 글자가 섞이지 않게 한다.

    Args:
        name: 품목명.

    Returns:
        str: 포함 문구를 뗀 이름.
    """
    return _INCLUDES_RE.sub("", name).strip()


class Scheme(StrEnum):
    """어린이제품 안전관리 제도. 값은 사용자에게 보여 줄 제도명이다."""

    CERTIFICATION = "안전인증"
    CONFIRMATION = "안전확인"
    SUPPLIER = "공급자적합성확인"


SCHEME_ANNEXES: dict[Scheme, tuple[int, int, str]] = {
    Scheme.CERTIFICATION: (1, 3, "cert"),
    Scheme.CONFIRMATION: (2, 4, "conf"),
    Scheme.SUPPLIER: (3, 5, "sdoc"),
}


@dataclass(frozen=True)
class ChildrenItem:
    """시행규칙 품목 행 하나와 거기에 이은 운용요령 적용범위 원문."""

    item_id: str
    scheme: Scheme
    name: str
    standards: tuple[str, ...]
    row_text: str
    scopes: tuple[str, ...] = ()
    scope_names: tuple[str, ...] = ()

    @property
    def short_name(self) -> str:
        """포함 문구를 뗀 품목명. 조회·순위·품목명 목록에 쓴다(근거 원문과 판단 제목은 name 그대로).

        Returns:
            str: 포함 문구를 뗀 이름.
        """
        return without_includes(self.name)

    @property
    def includes(self) -> tuple[str, ...]:
        """품목명에 붙은 포함 문구. 예: ("선글라스를 포함한다",).

        Returns:
            tuple[str, ...]: 포함 문구.
        """
        return tuple(match.group(1).strip() for match in _INCLUDES_RE.finditer(self.name))

    def as_candidate(self, scope_limit: int = _SCOPE_LIMIT) -> dict:
        """품목 선택 모델에 넘기는 모양. 적용범위는 길어서 잘라 넘긴다(근거는 코드가 원문을 붙인다).

        Args:
            scope_limit: 적용범위 최대 글자 수.

        Returns:
            dict: 행 ID·제도·품목명·적용 안전기준·적용범위.
        """
        scope = " ".join(self.scopes)
        return {"item_id": self.item_id, "scheme": self.scheme.value, "item": self.name,
                "standards": list(self.standards),
                "scope": scope[:scope_limit] + ("…" if len(scope) > scope_limit else "")}


@dataclass(frozen=True)
class Definitions:
    """법 제2조의 어린이제품 정의(제1호)와 공급자적합성확인대상 정의(제12호)."""

    law: DocRef
    children_product: str
    supplier_product: str


@dataclass(frozen=True)
class ChildrenEvidence:
    as_of: date
    definitions: Definitions
    rule: DocRef
    notice: DocRef
    items: tuple[ChildrenItem, ...]
    common_standard: ChildrenItem
    unlinked_scopes: tuple[str, ...]

    def documents(self) -> list[dict[str, str]]:
        """결과 query에 남길 문서 식별 정보.

        Returns:
            list[dict[str, str]]: 법·시행규칙·운용요령 순.
        """
        return [self.definitions.law.describe(), self.rule.describe(), self.notice.describe()]



def _law_item(body, article: int, label: str) -> str:
    """조문의 호(목 포함) 원문. 예: 제2조 제1호.

    Args:
        body: 법 본문 응답.
        article: 조 번호.
        label: 호 번호 글자 (예: "1.").

    Returns:
        str: 호 원문 (공백 정리).

    Raises:
        EvidenceUnavailable: 호를 찾지 못한 경우.
    """
    for candidate in body.articles:
        if str(candidate.article_number or "").lstrip("0") != str(article) or candidate.article_branch_number:
            continue
        for paragraph in candidate.paragraphs or []:
            for item in paragraph.items or []:
                if (item.number or "").strip() == label:
                    parts = [item.content or ""] + [sub.content or "" for sub in item.sub_items or []]
                    return normalize_text(" ".join(parts))
    raise EvidenceUnavailable(f"법 제{article}조 제{label.rstrip('.')}호를 찾지 못했습니다.")



def _cells(line: str) -> list[str] | None:
    """세로선으로 칸을 나눈다.

    Args:
        line: 별표 한 줄.

    Returns:
        list[str] | None: 칸 내용. 칸 줄이 아니면 None.
    """
    stripped = line.strip()
    if not stripped.startswith("│"):
        return None
    return [cell.strip() for cell in stripped.strip("│").split("│")]


def _is_separator(line: str) -> bool:
    """가로선 줄인지 본다. 세로로 쓴 병합 셀 글자(예: "│호├───")가 한두 자 섞여도 구분선으로 본다.

    Args:
        line: 별표 한 줄.

    Returns:
        bool: 가로선 줄이면 True.
    """
    return bool(re.search(r"[─━]", line)) and len(compact(line)) <= 2


def parse_rule_annex(text: str, scheme: Scheme) -> list[ChildrenItem]:
    """시행규칙 별표 1~3(품목 | 적용 안전기준)을 품목 행으로 나눈다. 삭제된 품목은 뺀다.

    칸 폭 때문에 줄이 끊긴 품목명·기준명("…(보" + "호 장구…)")은 공백 없이 잇는다.

    Args:
        text: 시행규칙 별표 원문.
        scheme: 이 별표가 정하는 제도.

    Returns:
        list[ChildrenItem]: 품목 행.

    Raises:
        EvidenceUnavailable: 품목을 하나도 찾지 못한 경우.
    """
    prefix = SCHEME_ANNEXES[scheme][2]
    rows: list[dict] = []
    for line in text.splitlines():
        cells = _cells(line)
        if cells is None or len(cells) < 2:
            continue
        left, right = cells[0], cells[-1]
        label = _LABEL_RE.match(left)
        if label:
            rows.append({"label": label.group(1), "name": label.group(2), "standards": [], "lines": []})
        elif rows and left:
            rows[-1]["name"] += left
        if not rows:
            continue
        rows[-1]["lines"].append(line)
        standard = _STANDARD_RE.match(right) if right else None
        if standard:
            rows[-1]["standards"].append(standard.group(2))
        elif right and rows[-1]["standards"]:
            rows[-1]["standards"][-1] += right
    items = []
    for row in rows:
        name = normalize_text(row["name"])
        if not name or _DELETED_RE.match(name):
            continue
        number = int(row["label"]) if row["label"].isdigit() else _KOREAN_LABELS.index(row["label"]) + 1
        standards = tuple(normalize_text(standard) for standard in row["standards"])
        items.append(ChildrenItem(
            item_id=f"{prefix}-{number:02d}", scheme=scheme, name=name, standards=standards,
            row_text=f"{row['label']}. {name} — 적용 안전기준: {', '.join(standards)}",
        ))
    if not items:
        raise EvidenceUnavailable(f"시행규칙 별표 {SCHEME_ANNEXES[scheme][0]}에서 품목을 찾지 못했습니다.")
    return items


def parse_scope_annex(text: str) -> list[tuple[str, str]]:
    """운용요령 별표 3~5(품목 | 적용범위)를 (품목명, 적용범위 원문) 덩어리로 나눈다.

    가로선 사이가 한 덩어리다. 품목 칸이 둘 이상으로 나뉜 곳(예: 스포츠보호용품 > 보호장구)은
    적용범위 바로 왼쪽 칸을 품목명으로 쓴다.

    Args:
        text: 운용요령 별표 원문.

    Returns:
        list[tuple[str, str]]: (품목명, 적용범위 원문).
    """
    blocks: list[list[list[str]]] = [[]]
    for line in text.splitlines():
        if _is_separator(line):
            blocks.append([])
            continue
        cells = _cells(line)
        if cells is not None and len(cells) >= 2:
            blocks[-1].append(cells)
    result = []
    for block in blocks:
        if not block:
            continue
        width = max(len(cells) for cells in block)
        name = "".join(cells[-2] for cells in block if len(cells) == width)
        scope = join_wrapped([cells[-1] for cells in block])
        if not compact(name) or compact(name) == "품목" or not scope:
            continue
        result.append((normalize_text(name), scope))
    return result


def _similarity(left: str, right: str) -> float:
    """글자 2개 조각 집합의 자카드 유사도.

    Args:
        left: 비교할 이름.
        right: 비교할 이름.

    Returns:
        float: 0~1 유사도. 한쪽이 비면 0.
    """
    a, b = set(bigrams(left)), set(bigrams(right))
    return len(a & b) / len(a | b) if a and b else 0.0


def link_scopes(items: list[ChildrenItem], scopes: list[tuple[str, str]]) -> tuple[list[ChildrenItem], list[str]]:
    """같은 제도 안에서 운용요령 품목을 시행규칙 품목에 잇는다.

    이름이 정확히 같지 않다(어린이용/아동용, 제품/용품, 띄어쓰기). 순서대로 잇는다.
    1. 공백을 뺀 이름이 같으면 잇는다.
    2. 운용요령 품목명이 시행규칙 품목명 안에 들어 있으면 잇는다(예: 보호장구 → "스포츠 보호용품(보호 장구 및 안전모)").
    3. 남은 것은 글자 유사도가 높은 쌍부터 하나씩 짝짓는다(시행규칙 품목 하나에 하나). 기준에 못 미치면 잇지 않고
       이름을 따로 돌려준다(사람 확인용).

    Args:
        items: 시행규칙 품목 행.
        scopes: 운용요령 (품목명, 적용범위 원문).

    Returns:
        tuple[list[ChildrenItem], list[str]]: (적용범위를 이은 품목 행, 잇지 못한 운용요령 품목명).
    """
    attached: dict[str, list[tuple[str, str]]] = {item.item_id: [] for item in items}
    remaining: list[tuple[str, str]] = []
    for scope_name, scope in scopes:
        key = compact(scope_name)
        exact = [item for item in items if compact(item.name) == key]
        contained = [item for item in items if len(key) > 1 and key in compact(item.name)]
        target = exact or (contained if len(contained) == 1 else [])
        if target:
            attached[target[0].item_id].append((scope_name, scope))
        else:
            remaining.append((scope_name, scope))
    pairs = sorted(((_similarity(item.name, name), index, item.item_id)
                    for index, (name, _) in enumerate(remaining) for item in items
                    if not attached[item.item_id]), reverse=True)
    used_scopes: set[int] = set()
    used_items: set[str] = set()
    for score, index, item_id in pairs:
        if score < _LINK_THRESHOLD or index in used_scopes or item_id in used_items:
            continue
        attached[item_id].append(remaining[index])
        used_scopes.add(index)
        used_items.add(item_id)
    unlinked = [name for index, (name, _) in enumerate(remaining) if index not in used_scopes]
    linked = [ChildrenItem(**{**item.__dict__,
                              "scopes": tuple(scope for _, scope in attached[item.item_id]),
                              "scope_names": tuple(name for name, _ in attached[item.item_id])})
              for item in items]
    return linked, unlinked


def common_standard_item(text: str) -> ChildrenItem:
    """시행규칙 별표 3 비고에서 개별 안전기준이 없는 품목의 기준을 행으로 만든다.

    Args:
        text: 시행규칙 별표 3 원문.

    Returns:
        ChildrenItem: 공통안전기준을 적용하는 공급자적합성확인 행.

    Raises:
        EvidenceUnavailable: 비고 문장을 찾지 못한 경우.
    """
    lines = [cells[0] for line in text.splitlines() if (cells := _cells(line)) is not None and len(cells) == 1]
    match = _COMMON_STANDARD_RE.search(join_wrapped(lines))
    if match is None:
        raise EvidenceUnavailable("시행규칙 별표 3에서 개별 안전기준이 없는 품목의 기준을 찾지 못했습니다.")
    sentence = match.group(0)
    return ChildrenItem(item_id="sdoc-common", scheme=Scheme.SUPPLIER,
                        name="개별 안전기준이 없는 공급자적합성확인대상어린이제품",
                        standards=("어린이제품 공통안전기준",), row_text=sentence)



def load_children_evidence(client: LawLookup, as_of: date) -> ChildrenEvidence:
    """법제처 API로 법·시행규칙·운용요령을 기준일 버전으로 받아 품목 행을 만든다(요청 6회).

    Args:
        client: 법제처 조회.
        as_of: 기준일.

    Returns:
        ChildrenEvidence: 기준일 근거 묶음.

    Raises:
        EvidenceUnavailable: 정의 조문이나 별표를 확인하지 못한 경우.
    """
    law = load_law(client, name=LAW_NAME, law_id=LAW_ID, as_of=as_of)
    rule = load_law(client, name=RULE_NAME, law_id=RULE_ID, as_of=as_of)
    notice = load_admrul(client, name=NOTICE_NAME, rule_id=NOTICE_ID, as_of=as_of)
    definitions = Definitions(law.ref, _law_item(law.body, 2, "1."), _law_item(law.body, 2, "12."))
    if "13세" not in compact(definitions.children_product):
        raise EvidenceUnavailable("법 제2조 제1호의 연령 기준을 확인하지 못했습니다.")

    items: list[ChildrenItem] = []
    unlinked: list[str] = []
    common = None
    for scheme, (rule_annex, notice_annex, _) in SCHEME_ANNEXES.items():
        rule_text = annex_text(rule.body, rule_annex)
        parsed = parse_rule_annex(rule_text, scheme)
        linked, missing = link_scopes(parsed, parse_scope_annex(annex_text(notice.body, notice_annex)))
        items.extend(linked)
        unlinked.extend(missing)
        if scheme is Scheme.SUPPLIER:
            common = common_standard_item(rule_text)
    if unlinked:
        # 법 개정으로 품목명이 바뀌면 적용범위가 조용히 빠질 수 있어 남긴다. 품목 행은 적용범위 없이 그대로 쓴다.
        logger.warning("어린이제품 운용요령 적용범위 %d개를 시행규칙 품목에 잇지 못했습니다: %s",
                       len(unlinked), ", ".join(unlinked))
    return ChildrenEvidence(as_of=as_of, definitions=definitions, rule=rule.ref, notice=notice.ref,
                            items=tuple(items), common_standard=common, unlinked_scopes=tuple(unlinked))
