"""방송통신기자재 적합성평가 근거: 전파법 제58조의2, 적합성평가 고시 별표 1(대상기자재), 시행령 별표 6의2(면제).

법제처 별표는 글자로 그린 표라 칸 줄이 어긋난다. 이 모듈이 법제처 응답을 직접 읽어 행을 만든다.
- 고시 별표 1은 무선설비 기기(1~10절)만 읽는다. 11절(전자파장해 기기, 유선 EMC)은 이번 범위 밖이다.
- 행 오른쪽 끝 10칸(적용분야 5칸, 적합성평가 유형 3칸, 기기부호, 기타사항)은 순서가 고정이라 오른쪽부터 센다.
  적합인증·적합등록·자기적합확인 구분은 모델이 아니라 이 칸 값으로 정한다.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from ..common.law import (
    DocRef, EvidenceUnavailable, LawLookup, annex_text, compact, law_paragraph, load_admrul, load_law,
    normalize_text,
)

LAW_NAME = "전파법"
LAW_ID = "001732"
DECREE_NAME = "전파법 시행령"
DECREE_ID = "004771"
NOTICE_NAME = "방송통신기자재등의 적합성평가에 관한 고시"
NOTICE_ID = "38724"

APPLIED_FIELDS = ("전자파적합성", "무선", "유선", "전자파흡수율", "전자파강도")
ASSESSMENT_TYPES = ("적합인증", "적합등록", "자기적합확인")
_TRAILING = len(APPLIED_FIELDS) + len(ASSESSMENT_TYPES) + 2
_WIRELESS_SECTIONS = range(1, 11)
_SECTION_RE = re.compile(r"^\s*(\d{1,2})\.\s+(\S.*?)\s*$")
_LABEL_RE = re.compile(r"^(?:[가-힣]\s*\.|\d{1,2}\s*\)|[가-힣]\s*\)|[①-⑳])")
_UNITS = {"㎑": 0.001, "kHz": 0.001, "KHz": 0.001, "㎒": 1.0, "MHz": 1.0, "㎓": 1000.0, "GHz": 1000.0}
_UNIT_RE = "|".join(re.escape(unit) for unit in _UNITS)
_BAND_RANGE_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*(?:{_UNIT_RE})?\s*(?:∼|~|-|–)\s*(\d+(?:\.\d+)?)\s*({_UNIT_RE})")
_BAND_SINGLE_RE = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNIT_RE})")
_PERSONAL_USE = "개인이사용할목적으로반입하는"
_BOX_SPLIT_RE = re.compile(r"[├┼┤┝┿┥─━┬┴]")


@dataclass(frozen=True)
class RadioItem:
    """고시 별표 1의 대상기자재 행 하나(가장 안쪽 분류)."""

    item_id: str
    section: str
    path: tuple[str, ...]
    assessment: tuple[str, ...]
    applied_fields: tuple[str, ...]
    code: str
    remark: str
    bands: tuple[tuple[float, float], ...]
    row_text: str

    @property
    def name(self) -> str:
        """사람이 읽을 기자재명. 맨 바깥 분류를 뺀 경로(번호 제외). 분류가 하나뿐이면 그 분류.

        Returns:
            str: " > "로 이은 기자재명.
        """
        parts = self.plain_path[1:] or self.plain_path or (self.section,)
        return " > ".join(parts)

    @property
    def plain_path(self) -> tuple[str, ...]:
        """번호(가., 1), 가))를 뗀 분류 경로. 조회·분류명 목록에 쓴다.

        Returns:
            tuple[str, ...]: 번호를 뗀 분류 경로.
        """
        return tuple(_LABEL_RE.sub("", part).strip() for part in self.path)

    def as_candidate(self) -> dict:
        """품목 선택 모델에 넘기는 모양.

        Returns:
            dict: 행 ID·절·분류 경로·평가 유형·적용 분야·대역(MHz)·비고.
        """
        return {"item_id": self.item_id, "section": self.section, "path": list(self.path),
                "assessment": list(self.assessment), "applied_fields": list(self.applied_fields),
                "bands_mhz": [list(band) for band in self.bands], "remark": self.remark}


@dataclass(frozen=True)
class Exemption:
    """시행령 별표 6의2의 면제대상 한 목."""

    part: str
    label: str
    target: str
    quantity: str
    content: str

    @property
    def text(self) -> str:
        """근거 인용에 쓸 목 한 줄.

        Returns:
            str: "가. 면제대상 (면제 수량: …, 면제 내용: …)" 모양의 글.
        """
        return f"{self.label}. {self.target} (면제 수량: {self.quantity}, 면제 내용: {self.content})"


@dataclass(frozen=True)
class RadioEvidence:
    as_of: date
    law: DocRef
    decree: DocRef
    notice: DocRef
    obligation: dict[str, str]
    items: tuple[RadioItem, ...]
    section_notes: dict[str, str] = field(default_factory=dict)
    personal_use: Exemption | None = None

    def documents(self) -> list[dict[str, str]]:
        """결과 query에 남길 문서 식별 정보.

        Returns:
            list[dict[str, str]]: 전파법·시행령·고시 순.
        """
        return [self.law.describe(), self.decree.describe(), self.notice.describe()]



def parse_bands(text: str) -> list[tuple[float, float]]:
    """주파수 표기를 MHz 범위로 읽는다. "5150∼5350㎒", "2.4GHz", "13.56㎒" 등. 단일 값은 (값, 값).

    Args:
        text: 주파수 표기가 든 글.

    Returns:
        list[tuple[float, float]]: (하한, 상한) MHz 범위. 소수 넷째 자리까지.
    """
    bands: list[tuple[float, float]] = []
    taken: list[tuple[int, int]] = []
    for match in _BAND_RANGE_RE.finditer(text):
        scale = _UNITS[match.group(3)]
        bands.append((float(match.group(1)) * scale, float(match.group(2)) * scale))
        taken.append(match.span())
    for match in _BAND_SINGLE_RE.finditer(text):
        if any(start <= match.start() < end for start, end in taken):
            continue
        value = float(match.group(1)) * _UNITS[match.group(2)]
        bands.append((value, value))
    return [(round(low, 4), round(high, 4)) for low, high in bands]



class _Label:
    """여러 줄에 걸친 분류 칸 글자를 모은다.

    Args:
        text: 첫 줄 글자.
    """

    def __init__(self, text: str):
        self.parts = [text]

    @property
    def text(self) -> str:
        """모은 글자를 이은 분류명.

        Returns:
            str: 공백 정리한 분류명.
        """
        return normalize_text("".join(self.parts))


def _is_full_separator(stripped: str) -> bool:
    """표 왼쪽 끝부터 그은 가로선 줄인지 본다.

    Args:
        stripped: 앞뒤 공백을 뗀 줄.

    Returns:
        bool: 가로선 줄이면 True.
    """
    return stripped[:1] in "├┝└┌┟┞"


def _section_rows(number: int, title: str, lines: list[str]) -> tuple[list[RadioItem], str]:
    """한 절의 표를 행으로 나눈다. 칸 머리(┝━ 줄 앞)는 건너뛴다.

    한 행 = 가로선 사이의 줄들. 바깥 분류 칸은 여러 행에 걸쳐 있어, 빈 칸은 위 행의 분류를 잇고
    부분 가로선 줄("│ │시스템용 ├──")의 왼쪽 글자도 그 분류에 이어 붙인다.

    Args:
        number: 절 번호.
        title: 절 제목.
        lines: 절 제목 다음 줄들.

    Returns:
        tuple[list[RadioItem], str]: (행, 절 비고). 표가 없으면 ([], "").
    """
    start = next((i for i, line in enumerate(lines) if "┝" in line), None)
    if start is None:
        return [], ""
    labels: list[_Label | None] = []
    block: list[list[str]] = []
    rows: list[tuple[list[_Label], list[list[str]]]] = []
    depth = 0
    notes: list[str] = []

    def put(column: int, text: str) -> None:
        nonlocal labels
        while len(labels) <= column:
            labels.append(None)
        if _LABEL_RE.match(text) or labels[column] is None:
            labels[column] = _Label(text)
            labels = labels[:column + 1]
        else:
            labels[column].parts.append(text)

    def flush() -> None:
        nonlocal block
        if block:
            rows.append(([label for label in labels[:depth] if label is not None], block))
        block = []

    for line in lines[start + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_full_separator(stripped):
            flush()
            continue
        if not stripped.startswith("│"):
            continue
        cells = stripped.strip("│").split("│")
        separator = next((i for i, cell in enumerate(cells) if re.search(r"[─━]", cell)), None)
        if separator is not None:
            leading = [*cells[:separator], _BOX_SPLIT_RE.split(cells[separator])[0]]
            for column, cell in enumerate(leading):
                if cell.strip():
                    put(column, cell.strip())
            flush()
            continue
        if len(cells) == 1:
            text = normalize_text(cells[0])
            if text:
                notes.append(text)
            continue
        if len(cells) <= _TRAILING:
            continue
        names = len(cells) - _TRAILING
        if not block:
            depth = names
        for column in range(names):
            if cells[column].strip():
                put(column, cells[column].strip())
        block.append(cells)
    flush()

    section = f"{number}. {normalize_text(title)}"
    items = []
    for index, (path_labels, block_cells) in enumerate(rows, start=1):
        marks = [any(cells[-_TRAILING + k].strip() for cells in block_cells) for k in range(_TRAILING - 2)]
        if not any(marks[5:8]) and "삭제" in compact(" ".join(label.text for label in path_labels)):
            continue
        code = "".join(cells[-2].strip() for cells in block_cells)
        remark = normalize_text(" ".join(cells[-1].strip() for cells in block_cells))
        path = tuple(label.text for label in path_labels)
        items.append(RadioItem(
            item_id=code or f"s{number}-{index:03d}", section=section, path=path,
            applied_fields=tuple(name for name, marked in zip(APPLIED_FIELDS, marks[:5]) if marked),
            assessment=tuple(name for name, marked in zip(ASSESSMENT_TYPES, marks[5:8]) if marked),
            code=code, remark=remark, bands=tuple(parse_bands(" ".join(path))),
            row_text=normalize_text(" ".join(" ".join(cells) for cells in block_cells)),
        ))
    return items, normalize_text(" ".join(notes))


def parse_radio_annex(text: str) -> tuple[list[RadioItem], dict[str, str]]:
    """고시 별표 1의 1~10절(무선설비 기기)을 행으로 나눈다.

    Args:
        text: 고시 별표 1 원문.

    Returns:
        tuple[list[RadioItem], dict[str, str]]: (행, 절별 비고).

    Raises:
        EvidenceUnavailable: 1~10절을 모두 찾지 못했거나 기기부호가 비었거나 겹치는 경우.
    """
    sections: list[tuple[int, str, list[str]]] = []
    for line in text.splitlines():
        match = _SECTION_RE.match(line)
        if match and not line.strip().startswith("│"):
            sections.append((int(match.group(1)), match.group(2), []))
        elif sections:
            sections[-1][2].append(line)
    items: list[RadioItem] = []
    notes: dict[str, str] = {}
    for number, title, lines in sections:
        if number not in _WIRELESS_SECTIONS:
            continue
        rows, note = _section_rows(number, title, lines)
        items.extend(rows)
        if note:
            notes[f"{number}. {normalize_text(title)}"] = note
    if len({number for number, _, _ in sections} & set(_WIRELESS_SECTIONS)) != len(_WIRELESS_SECTIONS):
        raise EvidenceUnavailable("고시 별표 1에서 무선설비 기기 절(1~10)을 모두 찾지 못했습니다.")
    codes = [item.code for item in items if item.code]
    if not items or len(codes) != len(set(codes)):
        raise EvidenceUnavailable("고시 별표 1의 기기부호가 비었거나 겹칩니다.")
    return items, notes


def parse_exemptions(text: str) -> list[Exemption]:
    """시행령 별표 6의2(면제대상 | 면제 수량 | 면제 내용)를 목 단위로 나눈다.

    면제 내용 칸은 여러 목에 걸친 병합 칸이라, 표 하나의 면제 내용을 이어 붙여 그 표의 모든 목에 쓴다.

    Args:
        text: 시행령 별표 6의2 원문.

    Returns:
        list[Exemption]: 면제대상 목.
    """
    parts: list[tuple[str, list[list[list[str]]]]] = []
    for line in text.splitlines():
        stripped = line.strip()
        heading = re.match(r"^(\d)\.\s*(법 제58조의3.*?면제대상 기자재)", stripped)
        if heading:
            parts.append((normalize_text(heading.group(0)), [[]]))
            continue
        if not parts or not stripped:
            continue
        cells = stripped.strip("│").split("│")
        separator = any(re.search(r"[─━]", cell) for cell in cells[:2])
        if _is_full_separator(stripped) or separator:
            tail = _BOX_SPLIT_RE.split(stripped.strip("│"))[-1].strip()
            if tail and parts[-1][1][-1]:
                parts[-1][1][-1].append(["", "", tail])
            parts[-1][1].append([])
            continue
        if stripped.startswith("│") and len(cells) >= 2:
            parts[-1][1][-1].append(cells)
    result: list[Exemption] = []
    for part, blocks in parts:
        rows = [block for block in blocks if block and not compact(block[0][0]).startswith("면제대상")]
        content = normalize_text("".join(cells[2].strip() for block in rows for cells in block if len(cells) > 2))
        for block in rows:
            target = normalize_text("".join(cells[0].strip() for cells in block))
            label = re.match(r"^([가-힣])\s*\.\s*", target)
            result.append(Exemption(
                part=part, label=label.group(1) if label else "", target=target[label.end():] if label else target,
                quantity=normalize_text("".join(cells[1].strip() for cells in block)), content=content,
            ))
    return result



def load_radio_evidence(client: LawLookup, as_of: date) -> RadioEvidence:
    """법제처 API로 전파법·시행령·고시를 기준일 버전으로 받아 대상기자재 행을 만든다(요청 6회).

    Args:
        client: 법제처 조회.
        as_of: 기준일.

    Returns:
        RadioEvidence: 기준일 근거 묶음.

    Raises:
        EvidenceUnavailable: 적합성평가 의무 조문이나 개인 사용 반입 면제를 확인하지 못한 경우.
    """
    law = load_law(client, name=LAW_NAME, law_id=LAW_ID, as_of=as_of)
    decree = load_law(client, name=DECREE_NAME, law_id=DECREE_ID, as_of=as_of)
    notice = load_admrul(client, name=NOTICE_NAME, rule_id=NOTICE_ID, as_of=as_of)
    obligation = {number: law_paragraph(law.body, 58, number, branch=2) for number in ("①", "②", "③", "④")}
    if "적합성평가" not in compact(obligation["①"]):
        raise EvidenceUnavailable("전파법 제58조의2 제1항의 적합성평가 의무를 확인하지 못했습니다.")
    items, notes = parse_radio_annex(annex_text(notice.body, 1))
    exemptions = parse_exemptions(annex_text(decree.body, 6, branch=2))
    personal = [exemption for exemption in exemptions if _PERSONAL_USE in compact(exemption.target)]
    if len(personal) != 1:
        raise EvidenceUnavailable("시행령 별표 6의2에서 개인 사용 반입 면제를 유일하게 찾지 못했습니다.")
    return RadioEvidence(as_of=as_of, law=law.ref, decree=decree.ref, notice=notice.ref, obligation=obligation,
                         items=tuple(items), section_notes=notes, personal_use=personal[0])
