"""전기용품 안전관리 근거(시행규칙·운용요령 고시)를 조회하고 품목표를 검토 단위로 나눈다.

판단 근거는 운용요령 고시 별표 1~3(안전인증·안전확인·공급자적합성확인 대상 세부품목)이다.
품목표는 표 테두리 문자로 그린 텍스트로 오므로, ┠ 선으로 나뉜 구간 하나를
"품목 묶음 + 그 묶음에 걸리는 비고"인 검토 단위(AnnexBlock)로 삼는다.
구간 단위로 자르면 비고가 어느 품목까지 적용되는지가 원문 그대로 유지된다.

근거 조회 경로는 ElectricalEvidenceSource로 추상화한다. 지금은 법제처 API(LawApiEvidenceSource)만
구현돼 있고, 적재 DB 경로(DatabaseEvidenceSource)는 테이블이 생긴 뒤 채울 자리만 둔다.
"""

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol, TypeVar
from xml.etree.ElementTree import ParseError

from pydantic import ValidationError

from ...schemas.clients.law_request import LawSearchRequest, LawTextRequest
from ...schemas.clients.law_response import AdmrulSearchResponse, LawSearchResponse, LawTextResponse

RULE_NAME = "전기용품 및 생활용품 안전관리법 시행규칙"
RULE_ID = "008044"
NOTICE_NAME = "전기용품 및 생활용품 안전관리 운용요령"
NOTICE_ID = "34911"

_BOX_CHARS = "┏┓┗┛┃┠┨┯┷┼┬┴├┤│─━"
_BOX_RE = re.compile(f"[{_BOX_CHARS}]")
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_ITEM_LABEL_RE = re.compile(r"^\s*([가-힣])\s*\.\s*")
_CATEGORY_RE = re.compile(r"^\s*(\d{1,2})\s*\.\s*(.*)$")
# 저전압 포함 비고. "교류전원 30V 이하, 직류전원 42V 이하에서 사용하는 것을 포함한다"처럼 둘 다이거나
# "직류전원 42V 이하에서 사용하는 것을 포함한다"처럼 한쪽만 적힌다. 공백을 지운 문장에 적용한다.
_LOW_VOLTAGE_AC_RE = re.compile(r"교류(?:전원)?30V이하")
_LOW_VOLTAGE_DC_RE = re.compile(r"직류(?:전원)?42V이하")


class Scheme(StrEnum):
    """전기용품 안전관리 제도. 값은 사용자에게 보여 줄 제도명이다."""

    CERTIFICATION = "안전인증"
    CONFIRMATION = "안전확인"
    SUPPLIER = "공급자적합성확인"


# 고시 별표 번호 → 제도. 안전성검사(별표 3의2)는 이번 범위에서 다루지 않는다.
SCHEME_ANNEXES: dict[Scheme, tuple[str, str]] = {
    Scheme.CERTIFICATION: ("0001", "안전인증대상전기용품"),
    Scheme.CONFIRMATION: ("0002", "안전확인대상전기용품"),
    Scheme.SUPPLIER: ("0003", "공급자적합성확인대상"),
}
_SCHEME_CODES = {Scheme.CERTIFICATION: "cert", Scheme.CONFIRMATION: "conf", Scheme.SUPPLIER: "sdoc"}


class EvidenceUnavailable(RuntimeError):
    """조회는 됐지만 필요한 문서·버전·본문을 확인할 수 없다. 조회 실패(네트워크·API 오류)와 구분한다."""


class LawLookupError(RuntimeError):
    """법제처가 유효한 응답을 주지 않았다(API 오류 응답·XML 아님·기본정보 없음·응답 형식 불일치).

    LawClient는 이런 경우 RuntimeError를 던진다. Client 호출 지점에서만 이 예외로 바꿔,
    Tool 내부의 버그(RuntimeError 계열)가 API 실패로 분류되지 않게 한다.
    """


class LawLookup(Protocol):
    """근거 조회에 필요한 LawClient 메서드만 선언한다. 테스트에서는 Fake로 바꾼다."""

    def search_law(self, request: LawSearchRequest) -> LawSearchResponse: ...
    def get_law_text(self, request: LawTextRequest) -> LawTextResponse: ...
    def search_admrul(self, request: LawSearchRequest) -> AdmrulSearchResponse: ...
    def get_admrul_text(self, request: LawTextRequest) -> LawTextResponse: ...


@dataclass(frozen=True)
class EvidenceSection:
    """인용 가능한 검토 단위 하나. LegalSource로 그대로 옮긴다."""

    source_id: str
    document_name: str
    document_id: str
    version_id: str
    effective_date: str
    section: str
    text: str
    source_url: str


@dataclass(frozen=True)
class AnnexBlock:
    """품목표의 검토 단위(┠ 구간 하나).

    Attributes:
        block_id: 모델과 코드가 함께 쓰는 식별자. 예: "conf-07-02".
        scheme: 이 품목표가 정하는 제도.
        category: 분류명. 예: "7. 전기기기".
        items: 품목명. 예: ["가. 과일 껍질깎이", "나. 전기 용해기"].
        sub_items: 세부품목명. 예: ["과일 껍질깎이", "왁스 용해기"].
        notes: 이 구간의 비고 원문.
        no_target: "대상 없음" 구간인지.
        includes_low_voltage_ac: 교류 30V 이하에서 쓰는 것도 포함한다는 비고가 있는지.
        includes_low_voltage_dc: 직류 42V 이하에서 쓰는 것도 포함한다는 비고가 있는지.
        section: 인용 원문과 출처.
    """

    block_id: str
    scheme: Scheme
    category: str
    items: tuple[str, ...]
    sub_items: tuple[str, ...]
    notes: tuple[str, ...]
    no_target: bool
    includes_low_voltage_ac: bool
    includes_low_voltage_dc: bool
    section: EvidenceSection


@dataclass(frozen=True)
class ElectricalEvidence:
    """한 기준일에 적용할 근거 묶음."""

    as_of: date
    rule_scope: EvidenceSection
    notice_scope: EvidenceSection
    blocks: tuple[AnnexBlock, ...]
    common_notes: dict[Scheme, EvidenceSection] = field(default_factory=dict)
    # 시행규칙 별표 13(구매대행의 특례 제품) 중 전기용품 부분. 확인하지 못하면 비어 있다.
    purchase_agent: dict[Scheme, EvidenceSection] = field(default_factory=dict)

    def block(self, block_id: str) -> AnnexBlock | None:
        return next((item for item in self.blocks if item.block_id == block_id), None)

    @property
    def documents(self) -> list[dict[str, str]]:
        """결과 query에 남길 문서 식별 정보. 본문·URL 파라미터의 키는 넣지 않는다."""
        sections = (self.rule_scope, self.notice_scope)
        return [{"id": item.document_id, "version": item.version_id, "effective_date": item.effective_date}
                for item in sections]


def normalize_text(text: str) -> str:
    """표 테두리와 공백만 정리한다. 품목·숫자·비고 문구는 바꾸지 않는다."""
    return re.sub(r"\s+", " ", _BOX_RE.sub(" ", text)).strip()


def compact(text: str) -> str:
    """이름 비교용. 공백과, API에서 깨져 오는 구분 문자(?·ㆍ)를 지운다."""
    return re.sub(r"[\s?·ㆍ]", "", text)


# -- 품목표 파싱 --
#
# 품목표의 칸 배치(3칸: 분류 │ 품목 │ 세부품목):
#   - "┠────" 줄은 분류 구간의 경계다.
#   - "│ 품목 ├────" 처럼 줄 중간의 ├ 는 그 오른쪽 칸들에서만 구분선이 시작된다는 뜻이다.
#     ├ 왼쪽 글자는 해당 칸의 내용으로 계속 이어진다.
#   - 구분선에 ┴ 가 있으면 다음 줄부터 품목·세부품목 칸이 합쳐진다(비고가 칸 두 개에 걸침).
#   - 세부품목 칸 안의 비고는 바로 위 품목 하나에, 칸이 합쳐진 비고는 그 앞 품목 묶음 전체에 걸린다.

@dataclass
class _Row:
    cells: list[str]          # 구분선 앞까지의 칸 내용
    sep_from: int | None      # 구분선이 시작되는 칸 번호. 내용만 있는 줄이면 None
    merges: bool              # 구분선 뒤로 품목·세부품목 칸이 합쳐지는지(┴)


def _parse_row(line: str) -> _Row | None:
    stripped = line.strip()
    if not stripped.startswith("┃"):
        return None
    inner = stripped[1:].rstrip()
    if inner.endswith(("┃", "│", "┨")):
        inner = inner[:-1]
    cells: list[str] = []
    for index, cell in enumerate(inner.split("│")):
        position = next((i for i, char in enumerate(cell) if char in "├─┼┴┬"), None)
        if position is None:
            cells.append(cell)
            continue
        cells.append(cell[:position])
        return _Row(cells, sep_from=index + 1, merges="┴" in cell[position:])
    return _Row(cells, sep_from=None, merges=False)


@dataclass
class _Unit:
    category: str
    name: str
    sub_text: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _split_sub_items(text: str) -> list[str]:
    """세부품목 칸을 ①②… 번호로 나눈다.

    법제처 응답에서 ⑯ 이후 번호는 "?"로 깨져 오므로, 앞이 공백인 "?"도 번호로 본다.
    ("정보?통신?"처럼 글자 사이의 "?"는 깨진 가운뎃점이라 나누지 않는다.)
    "삭제<…>"로 남은 세부품목은 넣지 않는다.
    """
    parts = re.split(f"[{_CIRCLED}]|(?:^|\\s)\\?(?=\\s)", text)
    items = (normalize_text(part).strip(" ?") for part in parts[1:])
    return [item for item in items if item and not compact(item).startswith("삭제")]


def _parse_units(text: str) -> tuple[list[_Unit], str]:
    """품목표를 품목 단위로 나누고, 표 끝의 공통 비고를 따로 돌려준다."""
    units: list[_Unit] = []
    common: list[str] = []
    category, category_rows = "", 0
    group_start = 0             # 칸이 합쳐진 비고가 적용될 품목 묶음의 시작 위치
    group_note: list[str] = []  # 진행 중인 합쳐진 비고
    note_mode: str | None = None  # "unit": 세부품목 칸 비고, "group": 합쳐진 비고
    merged_layout = False
    current: _Unit | None = None

    def close_group_note() -> None:
        nonlocal group_note, group_start
        if group_note:
            note = normalize_text(" ".join(group_note))
            for unit in units[group_start:]:
                unit.notes.append(note)
            group_start = len(units)
        group_note = []

    category_start = 0  # 현재 분류의 첫 품목 위치. 분류명이 이어 붙으면 그 품목들도 고친다.
    segment_start = 0   # 현재 ┠ 구간의 첫 품목 위치

    def take_category(cell: str) -> None:
        nonlocal category, category_rows, group_start, category_start
        label = normalize_text(cell)
        if not label:
            return
        match = _CATEGORY_RE.match(label)
        if match:
            name = f"{int(match.group(1))}. {normalize_text(match.group(2))}"
            if not category.startswith(f"{int(match.group(1))}. "):
                # 분류명은 구간 첫 줄이 아니라 몇 줄 아래(세로 가운데)에 적히기도 한다.
                # 같은 구간에서 분류명보다 먼저 나온 품목도 새 분류에 속한다.
                close_group_note()
                category, category_rows = name, 0
                group_start = category_start = segment_start
                for unit in units[segment_start:]:
                    unit.category = name
        elif category and category_rows <= 2 and not label.startswith("분류"):
            # 줄바꿈으로 끊긴 분류명("1. 전선 및 전원코" + "드")만 잇는다.
            category += label if re.match(r"[가-힣]", label) else f" {label}"
            for unit in units[category_start:]:
                unit.category = category

    def add_unit_note(fragment: str) -> None:
        # 여러 줄에 걸친 비고를 하나로 모은다. "비고"로 시작하면 새 비고다.
        if fragment.startswith("비고") or not current.notes:
            current.notes.append(fragment)
        else:
            current.notes[-1] = f"{current.notes[-1]} {fragment}"

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("┠", "┗")):
            close_group_note()
            note_mode, merged_layout, current = None, False, None
            group_start = segment_start = len(units)
            continue
        row = _parse_row(line)
        if row is None:
            continue
        cells = row.cells
        if len(cells) == 1 and row.sep_from is None:
            # 칸 구분이 없는 전체 폭 줄: 머리글 아래 공통 비고.
            if normalize_text(cells[0]):
                common.append(cells[0])
            continue
        if cells:
            take_category(cells[0])
        category_rows += 1
        if not category or normalize_text(cells[0]).startswith("분류"):
            continue
        body = cells[1:]
        if merged_layout and len(body) == 1:
            merged = normalize_text(body[0])
            if merged.startswith("비고") or note_mode == "group":
                note_mode = "group"
                group_note.append(merged)
            elif _ITEM_LABEL_RE.match(merged):
                current = _Unit(category, merged)
                units.append(current)
            elif merged and compact(merged) != "대상없음" and current is not None:
                current.name += merged
        elif body:
            second = normalize_text(body[0])
            third = " ".join(body[1:])
            if second.startswith("비고") or note_mode == "group":
                # 품목 칸에서 시작하는 비고는 앞 품목 묶음 전체에 걸친다.
                note_mode = "group"
                group_note.append(normalize_text(" ".join(body)))
                second = third = ""
            if second and compact(second) != "대상없음":
                if _ITEM_LABEL_RE.match(second) or current is None:
                    current = _Unit(category, second)
                    units.append(current)
                else:
                    current.name += second
            if third.strip() and current is not None:
                if normalize_text(third).startswith("비고") or note_mode == "unit":
                    note_mode = "unit"
                    add_unit_note(normalize_text(third))
                else:
                    current.sub_text.append(third)
        if row.sep_from is not None:
            if note_mode == "group":
                close_group_note()
            note_mode = None
            if row.sep_from <= 1:
                merged_layout = row.merges
                current = None if not row.merges else current
            elif row.sep_from == 2:
                merged_layout = row.merges
    close_group_note()
    return units, normalize_text(" ".join(common))


def parse_annex(text: str, scheme: Scheme, base: EvidenceSection) -> tuple[list[AnnexBlock], EvidenceSection | None]:
    """고시 품목표 하나를 품목 단위 검토 단위로 나눈다.

    Args:
        text: 별표 본문(annex_content).
        scheme: 이 별표가 정하는 제도.
        base: 문서·버전·URL을 물려줄 출처. section과 text만 품목마다 바꾼다.

    Returns:
        (품목 단위 목록, 표 끝의 공통 비고). 공통 비고가 없으면 None.
        삭제된 품목("삭제<...>")은 넣지 않는다.

    Raises:
        EvidenceUnavailable: 품목을 하나도 찾지 못한 경우.
    """
    units, common_text = _parse_units(text)
    blocks: list[AnnexBlock] = []
    per_category: dict[str, int] = {}
    for unit in units:
        name = normalize_text(unit.name)
        if compact(name).replace(".", "")[1:].startswith("삭제") or "<삭제>" in name:
            continue
        sub_items = _split_sub_items(" ".join(unit.sub_text))
        notes = tuple(dict.fromkeys(unit.notes))
        number = int(unit.category.split(".")[0])
        per_category[unit.category] = per_category.get(unit.category, 0) + 1
        block_id = f"{_SCHEME_CODES[scheme]}-{number:02d}-{per_category[unit.category]:02d}"
        # 인용문은 원문 칸을 정규화해 이은 발췌다. 품목·세부품목·비고 문구는 바꾸지 않는다.
        quote = " ".join(part for part in (
            unit.category, name, normalize_text(" ".join(unit.sub_text)), " ".join(notes),
        ) if part)
        blocks.append(AnnexBlock(
            block_id=block_id, scheme=scheme, category=unit.category,
            items=(name,), sub_items=tuple(sub_items), notes=notes, no_target=False,
            includes_low_voltage_ac=_includes_low_voltage(notes, _LOW_VOLTAGE_AC_RE),
            includes_low_voltage_dc=_includes_low_voltage(notes, _LOW_VOLTAGE_DC_RE),
            section=_section(base, f"{base.section} {unit.category} {name}", quote, source_id=block_id),
        ))
    if not blocks:
        raise EvidenceUnavailable("품목표에서 품목을 찾지 못했습니다.")
    common = _section(base, f"{base.section} 공통 비고", common_text) if common_text.startswith("비고") else None
    return blocks, common


def _includes_low_voltage(notes: tuple[str, ...], pattern: re.Pattern) -> bool:
    """비고가 저전압 제품을 '포함'한다고 정했는지. "30V 초과 … 한정"처럼 반대 뜻은 제외한다."""
    for note in notes:
        for sentence in re.split(r"(?<=다)\.|\d\.", compact(note)):
            if pattern.search(sentence) and "포함" in sentence:
                return True
    return False


def _section(base: EvidenceSection, label: str, text: str, *, source_id: str | None = None) -> EvidenceSection:
    return EvidenceSection(
        source_id=source_id or f"{base.source_id}-common", document_name=base.document_name,
        document_id=base.document_id, version_id=base.version_id, effective_date=base.effective_date,
        section=label, text=text, source_url=base.source_url,
    )


# -- 문서 버전 선택·본문 대조 --

def _day(value: str | None) -> date:
    if value is None or not re.fullmatch(r"[0-9]{8}", value):
        raise EvidenceUnavailable("시행일을 확인할 수 없습니다.")
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise EvidenceUnavailable("시행일 형식이 잘못됐습니다.") from exc


def select_version(result, *, name: str, identifier: str, id_field: str, name_field: str,
                   version_field: str, as_of: date):
    """검색 결과에서 기준일에 시행 중인 버전을 고른다.

    법령 ID와 이름이 정확히 일치하는 항목 중 시행일이 기준일 이하인 최신 버전을 쓴다.
    검색 첫 행·미래 시행 버전에 의존하지 않으며, 판단할 수 없으면 임의로 고르지 않는다.

    Raises:
        EvidenceUnavailable: 목록 불완전, 후보 없음, 같은 시행일에 버전이 둘 이상, 버전 번호 이상.
    """
    if result.total_count != len(result.items):
        raise EvidenceUnavailable("검색 목록이 불완전합니다.")
    candidates = []
    for item in result.items:
        if getattr(item, id_field) != identifier:
            continue
        if compact(getattr(item, name_field) or "") != compact(name):
            continue
        enforced = _day(item.enforce_date)
        if enforced <= as_of:
            candidates.append((enforced, item))
    if not candidates:
        raise EvidenceUnavailable("기준일에 적용할 문서 버전을 찾지 못했습니다.")
    latest_day = max(day for day, _ in candidates)
    latest = [item for day, item in candidates if day == latest_day]
    if len({getattr(item, version_field) for item in latest}) != 1:
        raise EvidenceUnavailable("같은 시행일의 문서 버전이 모호합니다.")
    selected = latest[0]
    version = getattr(selected, version_field)
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+", version):
        raise EvidenceUnavailable("문서 일련번호가 잘못됐습니다.")
    return selected


def _check_body(body: LawTextResponse, selected, *, name: str, identifier: str) -> None:
    if body.document_id != identifier or compact(body.name or "") != compact(name):
        raise EvidenceUnavailable("검색 문서와 본문 식별 정보가 다릅니다.")
    if body.enforce_date != selected.enforce_date:
        raise EvidenceUnavailable("검색 버전과 본문 시행일이 다릅니다.")


def article_text(body: LawTextResponse, number: int) -> str:
    """조문 하나의 전문을 원문 순서로 모은다.

    항 아래 호·목이 중첩된 응답(PR #248 이후)과 평평한 목록 응답(이전) 모두 처리한다.

    Raises:
        EvidenceUnavailable: 조문을 유일하게 찾지 못한 경우.
    """
    articles = [article for article in body.articles
                if str(article.article_number or "").lstrip("0") == str(number)
                and getattr(article, "article_branch_number", None) in (None, "", "0", "00")]
    if not articles:
        # 행정규칙 본문은 번호 필드 없이 조문내용만 오는 경우가 있다.
        articles = [article for article in body.articles
                    if (article.article_content or "").lstrip().startswith(f"제{number}조(")]
    if len(articles) != 1:
        raise EvidenceUnavailable(f"제{number}조를 유일하게 식별하지 못했습니다.")
    article = articles[0]
    parts = [article.article_content or ""]

    def collect(node) -> None:
        parts.append(getattr(node, "content", None) or "")
        for child_field in ("items", "sub_items"):
            for child in getattr(node, child_field, None) or []:
                collect(child)

    for node in getattr(article, "paragraphs", None) or []:
        collect(node)
    for child_field in ("items", "sub_items"):
        for node in getattr(article, child_field, None) or []:
            collect(node)
    return normalize_text(" ".join(parts))


def _annex_text(body: LawTextResponse, number: str, title: str) -> str:
    matches = [annex for annex in body.annexes
               if annex.annex_type == "별표" and annex.annex_number == number
               and annex.annex_branch_number in (None, "", "00")
               and compact(title) in compact(annex.annex_title or "")]
    if len(matches) != 1 or not (matches[0].annex_content or "").strip():
        raise EvidenceUnavailable(f"별표 {int(number)}의 본문을 확인하지 못했습니다.")
    return matches[0].annex_content


# -- 구매대행 특례 (법 제35조, 시행규칙 제56조·별표 13) --

# 별표 13의 전기용품 부분. 2호(생활용품)는 전기 Tool 범위가 아니다.
_PURCHASE_AGENT_PARTS: dict[Scheme, tuple[str, str]] = {
    Scheme.CERTIFICATION: (r"1\.\s*안전인증대상\s*전기용품", r"2\.\s*안전인증대상\s*생활용품"),
    Scheme.CONFIRMATION: (r"3\.\s*안전확인대상\s*전기용품", r"$"),
}


def parse_purchase_agent(body: LawTextResponse, base: EvidenceSection) -> dict[Scheme, EvidenceSection]:
    """시행규칙 별표 13에서 제도별 구매대행 특례 품목 목록(원문)을 잘라 낸다.

    별표가 없거나 구획을 찾지 못하면 빈 dict를 돌려준다. 구매대행 안내만 빠지고 품목 판단은 계속한다.
    공급자적합성확인대상은 법 제35조가 정하지 않으므로 목록이 없다.
    """
    matches = [annex for annex in body.annexes
               if annex.annex_type == "별표" and annex.annex_number == "0013"
               and annex.annex_branch_number in (None, "", "00")
               and "구매대행" in compact(annex.annex_title or "")]
    if len(matches) != 1 or not (matches[0].annex_content or "").strip():
        return {}
    text = normalize_text(matches[0].annex_content)
    parts: dict[Scheme, EvidenceSection] = {}
    for scheme, (start, end) in _PURCHASE_AGENT_PARTS.items():
        found = re.search(f"{start}(.*?)(?={end})", text, flags=re.S)
        if found is None:
            return {}
        parts[scheme] = _section(base, f"별표 13 {scheme.value}대상 전기용품", normalize_text(found.group(0)),
                                 source_id=f"rule-annex13-{_SCHEME_CODES[scheme]}")
    return parts


def purchase_agent_status(block: AnnexBlock, part: EvidenceSection | None) -> tuple[str, str]:
    """품목 행이 별표 13 구매대행 특례 목록에 이름으로 올라 있는지 본다.

    Returns:
        (상태, 목록의 해당 문구). 상태는
        "listed"(이름이 있음), "listed_with_exclusion"(이름 뒤에 "…는 제외한다"가 붙음),
        "unmatched"(이름으로 대응시키지 못함. 표현이 달라 못 찾았을 수 있으므로 "특례 없음"으로 보지 않는다.
        특례 없음을 확정하려면 사람이 검토한 대응 규칙이 필요하다),
        "similar_clause"(품목표의 "그 밖에 … 유사한 기기" 행. 목록의 유사 기기 조항 해당 여부는 사람이 확인),
        "unknown"(목록을 확인하지 못했거나 공급자적합성확인대상).
    """
    if part is None:
        return "unknown", ""
    name = re.sub(r"^[가-힣]\s*\.\s*", "", block.items[0]) if block.items else ""
    if compact(name).startswith("그밖에"):
        return "similar_clause", ""
    # "나. 전기기기용 스위치 대상 없음"처럼 분류명만 있고 품목이 없는 줄은 지운다(분류명에 걸리지 않게).
    listing = compact(re.sub(r"[가-하]\.\s*[^.]*?대상\s*없음", " ", part.text))
    # "전기담요 및 매트,전기침대"처럼 묶인 품목명은 앞부분으로도 찾는다(목록에서는 괄호로 일부를 제외한다).
    candidates = [compact(name)] + [compact(part_name) for part_name in re.split(r"[,，]", name)]
    for candidate in dict.fromkeys(c for c in candidates if len(c) >= 3):
        position = listing.find(candidate)
        if position < 0:
            continue
        rest = listing[position + len(candidate):]
        quoted = candidate
        if rest.startswith("("):
            closing = rest.find(")")
            quoted += rest[:closing + 1] if closing > 0 else ""
        status = "listed_with_exclusion" if "제외" in quoted else "listed"
        return status, quoted
    return "unmatched", ""


# -- 근거 조회 경로 --

class ElectricalEvidenceSource(Protocol):
    """기준일에 적용할 전기용품 근거를 돌려준다."""

    def load(self, as_of: date) -> ElectricalEvidence: ...


_R = TypeVar("_R")


def _lookup(call: Callable[..., _R], request) -> _R:
    """Client 호출 하나를 실행한다. httpx 오류는 그대로 올려 호출자가 HTTP 상태별로 분류한다."""
    try:
        return call(request)
    except (RuntimeError, ParseError, ValidationError) as exc:
        raise LawLookupError(f"법제처 응답을 확인하지 못했습니다 ({type(exc).__name__}).") from exc


class LawApiEvidenceSource:
    """법제처 API로 시행규칙·운용요령을 조회한다. 실행마다 4회 요청하므로 CachedEvidenceSource로 감싼다.

    Args:
        law_client: LawClient 또는 같은 메서드를 가진 객체. 생성·close는 호출자가 맡는다.
    """

    def __init__(self, law_client: LawLookup):
        self._client = law_client

    def load(self, as_of: date) -> ElectricalEvidence:
        rule = select_version(
            _lookup(self._client.search_law, LawSearchRequest(query=RULE_NAME, display=100)),
            name=RULE_NAME, identifier=RULE_ID, id_field="law_id", name_field="law_name",
            version_field="mst", as_of=as_of,
        )
        rule_body = _lookup(self._client.get_law_text, LawTextRequest(mst=rule.mst))
        _check_body(rule_body, rule, name=RULE_NAME, identifier=RULE_ID)
        notice = select_version(
            _lookup(self._client.search_admrul, LawSearchRequest(query=NOTICE_NAME, display=100)),
            name=NOTICE_NAME, identifier=NOTICE_ID, id_field="rule_id", name_field="name",
            version_field="serial_number", as_of=as_of,
        )
        notice_body = _lookup(self._client.get_admrul_text, LawTextRequest(mst=notice.serial_number))
        _check_body(notice_body, notice, name=NOTICE_NAME, identifier=NOTICE_ID)

        # 법령 링크는 버전(MST)을 고정한 공개 열람 주소다. 요청 URL(OC 포함)은 쓰지 않는다.
        rule_url = f"https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq={rule.mst}"
        notice_url = f"https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq={notice.serial_number}"
        rule_scope = EvidenceSection("rule-art3", RULE_NAME, RULE_ID, rule.mst, rule.enforce_date,
                                     "제3조", article_text(rule_body, 3), rule_url)
        notice_scope = EvidenceSection("notice-art3", NOTICE_NAME, NOTICE_ID, notice.serial_number,
                                       notice.enforce_date, "제3조", article_text(notice_body, 3), notice_url)
        # 범위 조문에 판단에 쓰는 조건이 실제로 있는지 확인한다(빈 본문·다른 조문 방어).
        if not all(token in compact(rule_scope.text) for token in ("1천볼트", "별표3", "별표4", "별표5")):
            raise EvidenceUnavailable("시행규칙 제3조의 대상 범위를 확인하지 못했습니다.")
        if not all(token in compact(notice_scope.text) for token in ("30V이하", "42V이하", "제외", "비고")):
            raise EvidenceUnavailable("고시 제3조의 저전압 제외 조건을 확인하지 못했습니다.")

        blocks: list[AnnexBlock] = []
        common: dict[Scheme, EvidenceSection] = {}
        for scheme, (number, title) in SCHEME_ANNEXES.items():
            base = EvidenceSection(f"{_SCHEME_CODES[scheme]}", NOTICE_NAME, NOTICE_ID, notice.serial_number,
                                   notice.enforce_date, f"별표 {int(number)}", "", notice_url)
            parsed, note = parse_annex(_annex_text(notice_body, number, title), scheme, base)
            if not any(block.sub_items for block in parsed):
                raise EvidenceUnavailable(f"별표 {int(number)}에서 세부품목을 찾지 못했습니다.")
            blocks.extend(parsed)
            if note is not None:
                common[scheme] = note
        rule_base = EvidenceSection("rule-annex13", RULE_NAME, RULE_ID, rule.mst, rule.enforce_date,
                                    "별표 13", "", rule_url)
        return ElectricalEvidence(as_of=as_of, rule_scope=rule_scope, notice_scope=notice_scope,
                                  blocks=tuple(blocks), common_notes=common,
                                  purchase_agent=parse_purchase_agent(rule_body, rule_base))


class CachedEvidenceSource:
    """근거를 기준일별로 캐시한다. 여러 요청이 동시에 와도 한 번만 조회한다.

    법령은 하루에도 개정·시행될 수 있으므로 기준일을 키로 쓰고, ttl_seconds가 지나면 다시 조회한다.
    조회 실패는 캐시하지 않는다.

    Args:
        source: 실제 조회 경로.
        ttl_seconds: 캐시 유지 시간. 기본 6시간.
        clock: 테스트용 시계.
    """

    def __init__(self, source: ElectricalEvidenceSource, *, ttl_seconds: float = 6 * 3600,
                 clock: Callable[[], float] = time.monotonic):
        self._source = source
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[date, tuple[float, ElectricalEvidence]] = {}

    def load(self, as_of: date) -> ElectricalEvidence:
        with self._lock:
            cached = self._cache.get(as_of)
            if cached is not None and self._clock() - cached[0] < self._ttl:
                return cached[1]
            evidence = self._source.load(as_of)
            # 기준일이 바뀌면 이전 날짜는 다시 쓰지 않으므로 하나만 남긴다.
            self._cache = {as_of: (self._clock(), evidence)}
            return evidence


class DatabaseEvidenceSource:
    """적재 DB에서 근거를 읽는 경로. 아직 테이블이 없어 자리만 둔다.

    현재 DB(laws, law_articles)에는 조문만 있고 행정규칙·별표가 없다. 이 경로를 쓰려면 다음이 먼저 필요하다.

    - 행정규칙(운용요령) 메타 테이블: 문서 ID, 일련번호, 시행일, 현행 여부
    - 별표 테이블: 문서 버전 FK, 별표번호·가지번호·구분·제목, 본문 원문
    - 위 테이블을 채우는 적재 작업(LawClient.get_admrul_text 결과 저장)

    구현 후에는 같은 ElectricalEvidence를 만들어 돌려주면 ElectricalTool을 바꾸지 않고 교체할 수 있다.
    파싱은 parse_annex, 버전 선택은 select_version을 그대로 쓴다.

    Args:
        session_factory: app.database.get_session_factory()가 돌려주는 세션 팩토리.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def load(self, as_of: date) -> ElectricalEvidence:
        # TODO: 별표·행정규칙 테이블과 적재 작업이 생기면 구현한다.
        raise NotImplementedError("DB 근거 경로는 별표·행정규칙 테이블 적재 후 구현합니다.")
