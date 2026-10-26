"""식약 Tool 근거(식품·화장품·의료기기 관련 법령과 고시)를 조회하고 읽는다.

- 식품용 기구·용기, 식품·건강기능식품: 식품위생법 제2조 제1호·제4호·제5호(정의), 건강기능식품에 관한 법률 제3조(정의),
  수입식품안전관리 특별법 제2조 제1호(수입식품등에 건강기능식품 포함)·제14조(영업 종류: 수입·판매업, 인터넷 구매 대행업)·
  제15조(영업등록)·제20조(판매 목적 수입신고), 같은 법 시행령 제2조(영업의 범위).
- 화장품: 화장품법 제2조(화장품·기능성화장품 정의)·제3조(영업등록)·제4조(기능성화장품 심사·보고)·
  제8조(사용할 수 없는 원료)·제15조(판매 금지, 수입대행 알선 포함), 제2조 제11호(책임판매업: 수입대행형 거래 알선 포함),
  시행규칙 제2조(기능성화장품 범위), 「화장품 안전기준 등에 관한 규정」 제3조·별표 1(사용할 수 없는 원료).
- 의료기기: 의료기기법 제2조(정의)·제15조(수입업허가, 품목 수입허가·인증·신고)·제17조(판매업신고)·
  제26조(허가 없는 의료기기 판매 금지, 의료기기 오인 표시·광고 금지), 같은 법 시행규칙 제32조(자가 사용용 등 수입허가 면제),
  「의료기기 품목 및 품목별 등급에 관한 규정」 별표 1(품목·등급).
"""

import re
from dataclasses import dataclass
from functools import cached_property
from datetime import date

from ..common.law import (
    DocRef, EvidenceUnavailable, LawDocument, LawLookup, annex_text, article_text, join_wrapped, load_admrul, load_law,
    normalize_text,
)

FOOD_ACT = ("식품위생법", "001805")
IMPORTED_FOOD_ACT = ("수입식품안전관리 특별법", "012247")
IMPORTED_FOOD_DECREE = ("수입식품안전관리 특별법 시행령", "012486")
DEVICE_ACT = ("의료기기법", "009514")
DEVICE_RULE = ("의료기기법 시행규칙", "009740")
DEVICE_NOTICE = ("의료기기 품목 및 품목별 등급에 관한 규정", "32269")
HEALTH_FOOD_ACT = ("건강기능식품에 관한 법률", "009353")
COSMETICS_ACT = ("화장품법", "002015")
COSMETICS_RULE = ("화장품법 시행규칙", "008741")
COSMETICS_NOTICE = ("화장품 안전기준 등에 관한 규정", "37098")

_ITEM_RE = re.compile(r"^([A-Z]\d{5}\.\d{2})\s+(.+?)\s*\[(\d)\]\s*(.*)$")
_GROUP_RE = re.compile(r"^([A-Z]\d{5})\s+(.*)$")
_HANGUL_RE = re.compile(r"[가-힣]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_NUMBERED_RE = re.compile(r"(?:^|\s)(\d{1,2})\.\s")
_SALT_SUFFIX_RE = re.compile(r"\s*및\s*그\s*(?:염류|염|화합물|에스텔류|에스터류|유도체)$")
_FOOTNOTE_RE = re.compile(r"\s*\d\)$")
# 원료명에 사용 조건이 붙은 행(예: "석면기준에 적합하지 않은 탤크", "과산화물가가 …를 초과하는 리모넨", "(다만, … 제외)").
# 이름만 같아서는 금지 원료라고 할 수 없어 조건 확인으로 낮춘다.
_CONDITION_RE = re.compile(r"(적합하지|초과|이하|이상|다만|제외|함유|경우|에 한|\s중\s|만 해당)")
_DOTS = str.maketrans("", "", "·ㆍ?・")


@dataclass(frozen=True)
class Article:
    """근거 조문 한 부분(문서 버전 + 조문 위치 + 판단에 쓰는 항·호의 원문)."""

    doc: DocRef
    label: str
    text: str

    def source(self):
        return self.doc.source(self.label, self.text)


@dataclass(frozen=True)
class DeviceItem:
    """의료기기 품목 및 품목별 등급 규정 별표 1의 품목 한 행.

    Attributes:
        item_id: 품목 분류번호. 예: "A11010.01".
        name: 한글 품목명.
        grade: 등급(1~4).
        english: 영문 품목명.
        definition: 품목 정의(한글).
        group: 중분류 이름. 예: "체온계".
    """

    item_id: str
    name: str
    grade: int
    english: str
    definition: str
    group: str

    @property
    def row_text(self) -> str:
        return f"{self.item_id} {self.name} [{self.grade}등급] {self.definition}"

    def as_candidate(self) -> dict:
        return {"item_id": self.item_id, "name": self.name, "group": self.group, "definition": self.definition[:200]}


@dataclass(frozen=True)
class FunctionalType:
    """화장품법 시행규칙 제2조의 기능성화장품 범위 한 호."""

    number: int
    text: str


@dataclass(frozen=True)
class BannedIngredient:
    """「화장품 안전기준 등에 관한 규정」 별표 1(사용할 수 없는 원료)의 한 행.

    Attributes:
        name: 원료명 칸. 예: "구아네티딘 및 그 염류".
        cas: CAS 번호 칸(여러 개일 수 있음, "-"는 뺀다).
        chemicals: 화학물질명 칸.
    """

    name: str
    cas: tuple[str, ...]
    chemicals: tuple[str, ...]

    @property
    def row_text(self) -> str:
        parts = [self.name]
        if self.cas:
            parts.append("CAS " + ", ".join(self.cas))
        if self.chemicals:
            parts.append("화학물질명 " + ", ".join(self.chemicals))
        return " / ".join(parts)

    @property
    def conditional(self) -> bool:
        """원료명에 사용 조건(함량·기준·제외)이 붙어 이름만으로는 금지 여부를 정할 수 없는 행인지."""
        return bool(_CONDITION_RE.search(self.name))

    def names(self) -> list[str]:
        """대조에 쓰는 이름: 원료명, 각주·"및 그 염류"를 뗀 원료명, 화학물질명."""
        base = _SALT_SUFFIX_RE.sub("", _FOOTNOTE_RE.sub("", self.name))
        return list(dict.fromkeys([self.name, base, *self.chemicals]))


def ingredient_key(name: str) -> str:
    """성분명 비교용 키. 공백·가운뎃점·대소문자 차이를 무시한다."""
    return "".join(name.split()).translate(_DOTS).lower()


@dataclass(frozen=True)
class FoodDrugEvidence:
    """한 기준일에 적용할 식약 근거 묶음."""

    food_item: Article
    imported_scope: Article
    health_food: Article
    food_definition: Article
    import_business: Article
    import_registration: Article
    import_report: Article
    import_business_scope: Article
    device_definition: Article
    device_import: Article
    device_sale: Article
    device_unapproved: Article
    device_misleading: Article
    device_exemption: Article
    device_notice: DocRef
    devices: tuple[DeviceItem, ...]
    cosmetic_definition: Article
    functional_definition: Article
    cosmetic_business: Article
    cosmetic_business_scope: Article
    functional_review: Article
    cosmetic_ban: Article
    cosmetic_sale_ban: Article
    functional_scope: Article
    functional_types: tuple[FunctionalType, ...]
    cosmetic_notice: Article
    banned: tuple[BannedIngredient, ...]

    def device(self, item_id: str) -> DeviceItem | None:
        return next((item for item in self.devices if item.item_id == item_id), None)

    def functional(self, number: int) -> FunctionalType | None:
        return next((item for item in self.functional_types if item.number == number), None)

    @cached_property
    def _banned_index(self) -> dict[str, BannedIngredient]:
        """이름 키 → 원료 행. 처음 대조할 때 한 번 만든다(행마다 키를 다시 만들면 성분 하나에 수십 ms가 걸렸다)."""
        index: dict[str, BannedIngredient] = {}
        for row in self.banned:
            for name in row.names():
                index.setdefault(ingredient_key(name), row)
        return index

    def banned_match(self, ingredient: str) -> BannedIngredient | None:
        """성분명이 사용할 수 없는 원료의 이름과 같으면 그 행. 글자 대조라 다른 이름(영문명·이명)은 찾지 못한다."""
        key = ingredient_key(ingredient)
        return self._banned_index.get(key) if key else None

    def documents(self) -> list[dict[str, str]]:
        refs = {article.doc.document_id: article.doc for article in (
            self.food_item, self.health_food, self.import_business, self.import_business_scope,
            self.device_definition, self.device_exemption, self.cosmetic_definition, self.cosmetic_business_scope,
            self.functional_scope, self.cosmetic_notice)}
        refs[self.device_notice.document_id] = self.device_notice
        return [ref.describe() for ref in refs.values()]


def parse_device_items(text: str) -> list[DeviceItem]:
    """품목·등급 별표 1을 품목 행으로 나눈다. 삭제·번호 변경 줄과 중분류 머리 줄은 품목으로 넣지 않는다.

    한 줄 형식: "A11010.01  전자 체온계 [2]  Thermometer, … 체온을 측정하는 …".
    등급 뒤 글은 영문 품목명과 한글 정의다. 첫 한글 글자부터를 정의로 본다.

    Raises:
        EvidenceUnavailable: 품목을 찾지 못한 경우.
    """
    items: list[DeviceItem] = []
    group = ""
    for line in text.splitlines():
        stripped = normalize_text(line)
        matched = _ITEM_RE.match(stripped)
        if matched:
            item_id, name, grade, rest = matched.groups()
            hangul = _HANGUL_RE.search(rest)
            english = rest[:hangul.start()].strip() if hangul else rest.strip()
            definition = rest[hangul.start():].strip() if hangul else ""
            items.append(DeviceItem(item_id, name.strip(), int(grade), english, definition, group))
            continue
        header = _GROUP_RE.match(stripped)
        if header:
            label = header.group(2)
            latin = _LATIN_RE.search(label)
            group = (label[:latin.start()] if latin else label).strip()
    if not items:
        raise EvidenceUnavailable("의료기기 품목·등급 별표에서 품목을 찾지 못했습니다.")
    return items


def parse_functional_types(article: str) -> list[FunctionalType]:
    """화장품법 시행규칙 제2조(기능성화장품의 범위)를 호별로 나눈다.

    Raises:
        EvidenceUnavailable: 호를 찾지 못한 경우.
    """
    body = article.split("다음 각 호의 화장품을 말한다.", 1)
    if len(body) != 2:
        raise EvidenceUnavailable("화장품법 시행규칙 제2조의 기능성화장품 범위를 찾지 못했습니다.")
    parts = _NUMBERED_RE.split(" " + body[1])
    types = [FunctionalType(int(number), text.strip()) for number, text in zip(parts[1::2], parts[2::2]) if text.strip()]
    if not types:
        raise EvidenceUnavailable("화장품법 시행규칙 제2조의 기능성화장품 범위가 비어 있습니다.")
    return types


def parse_banned_ingredients(text: str) -> list[BannedIngredient]:
    """「화장품 안전기준 등에 관한 규정」 별표 1(사용할 수 없는 원료) 표를 원료 행으로 나눈다.

    표는 '원료명 │ CAS No. │ 화학물질명' 세 칸이고, 줄 맨 앞의 ├ 줄이 원료 경계다(칸 안의 ├는 같은 원료의 CAS 구분).
    칸 폭 때문에 끊긴 원료명은 이어 붙인다. 머리글은 넣지 않는다.

    Raises:
        EvidenceUnavailable: 원료를 찾지 못한 경우.
    """
    rows: list[BannedIngredient] = []
    name: list[str] = []
    cas: list[str] = []
    chemical: list[list[str]] = [[]]

    def flush() -> None:
        label = join_wrapped(name)
        if label and label != "원료명":
            numbers = tuple(number for number in (normalize_text(value) for value in cas) if number and number != "-")
            chemicals = tuple(value for value in (join_wrapped(part) for part in chemical) if value)
            rows.append(BannedIngredient(label, numbers, chemicals))
        name.clear()
        cas.clear()
        chemical[:] = [[]]

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("├", "┌", "└")):
            flush()
            continue
        if not stripped.startswith("│"):
            continue
        cells = stripped.split("│")
        if "├" in stripped:
            # "│(원료명 칸)  ├────┼────┤": 같은 원료의 다음 CAS 행이 시작된다(├가 칸 구분 │ 자리를 대신한다).
            name.append(stripped[1:stripped.index("├")])
            chemical.append([])
            continue
        if len(cells) < 4:
            continue
        name.append(cells[1])
        if cells[2].strip():
            cas.append(cells[2])
        chemical[-1].append(cells[3])
    flush()
    if not rows:
        raise EvidenceUnavailable("화장품 사용할 수 없는 원료 별표에서 원료를 찾지 못했습니다.")
    return rows


def _article(document: LawDocument, number: int, label: str, start: str | None = None, end: str | None = None,
             ) -> Article:
    """조문 전문에서 판단에 쓰는 부분(start부터 end 앞까지)만 잘라 근거로 만든다.

    Raises:
        EvidenceUnavailable: 조문이나 잘라 낼 문구를 찾지 못한 경우(빈 본문·다른 조문·개정으로 문구가 바뀐 경우).
    """
    text = article_text(document.body, number)
    begin = 0 if start is None else text.find(start)
    if begin < 0:
        raise EvidenceUnavailable(f"{document.name} 제{number}조에서 '{start}'를 찾지 못했습니다.")
    finish = len(text) if end is None else text.find(end, begin + 1)
    if finish < 0:
        raise EvidenceUnavailable(f"{document.name} 제{number}조에서 '{end}'를 찾지 못했습니다.")
    return Article(document.ref, f"제{number}조{label}", text[begin:finish].strip())


def load_food_drug_evidence(client: LawLookup, as_of: date) -> FoodDrugEvidence:
    """법제처에서 식약 근거 문서 10개를 기준일 버전으로 받는다.

    조문마다 판단에 쓰는 항·호만 잘라 인용한다. 잘라 낼 문구가 없으면 근거로 쓰지 않는다.

    Raises:
        EvidenceUnavailable: 문서·버전·조문·별표를 확인할 수 없는 경우.
        LawLookupError, httpx.HTTPError: 조회 자체가 실패한 경우.
    """
    food = load_law(client, name=FOOD_ACT[0], law_id=FOOD_ACT[1], as_of=as_of)
    imported = load_law(client, name=IMPORTED_FOOD_ACT[0], law_id=IMPORTED_FOOD_ACT[1], as_of=as_of)
    decree = load_law(client, name=IMPORTED_FOOD_DECREE[0], law_id=IMPORTED_FOOD_DECREE[1], as_of=as_of)
    device = load_law(client, name=DEVICE_ACT[0], law_id=DEVICE_ACT[1], as_of=as_of)
    rule = load_law(client, name=DEVICE_RULE[0], law_id=DEVICE_RULE[1], as_of=as_of)
    notice = load_admrul(client, name=DEVICE_NOTICE[0], rule_id=DEVICE_NOTICE[1], as_of=as_of)
    health = load_law(client, name=HEALTH_FOOD_ACT[0], law_id=HEALTH_FOOD_ACT[1], as_of=as_of)
    cosmetics = load_law(client, name=COSMETICS_ACT[0], law_id=COSMETICS_ACT[1], as_of=as_of)
    cosmetics_rule = load_law(client, name=COSMETICS_RULE[0], law_id=COSMETICS_RULE[1], as_of=as_of)
    safety = load_admrul(client, name=COSMETICS_NOTICE[0], rule_id=COSMETICS_NOTICE[1], as_of=as_of)
    functional_scope = _article(cosmetics_rule, 2, "", "제2조(기능성화장품의 범위)")
    return FoodDrugEvidence(
        food_item=_article(food, 2, " 제1호", '1. "식품"이란', '2. "식품첨가물"'),
        imported_scope=_article(imported, 2, " 제1호", '1. "수입식품등"이란', "1의2."),
        health_food=_article(health, 3, " 제1호·제2호", '1. "건강기능식품"이란', "3. 삭제"),
        food_definition=_article(food, 2, " 제4호·제5호", '4. "기구"란', "5의2."),
        import_business=_article(imported, 14, " 제1항", "① 다음 각 호의 영업", "②"),
        import_registration=_article(imported, 15, " 제1항", "① 제14조제1항", "②"),
        import_report=_article(imported, 20, " 제1항", "① 영업자가 판매를 목적으로", "②"),
        import_business_scope=_article(decree, 2, " 제1호·제3호", "1. 수입식품등 수입ㆍ판매업", "4. 수입식품등 보관업"),
        device_definition=_article(device, 2, " 제1항", '① 이 법에서 "의료기기"란', "②"),
        device_import=_article(device, 15, " 제1항·제2항", "① 의료기기의 수입을 업으로", "③"),
        device_sale=_article(device, 17, " 제1항·제2항", "① 의료기기의 판매를 업으로", "③"),
        device_unapproved=_article(device, 26, " 제1항", "① 누구든지", "② 누구든지"),
        # 시행일이 나뉜 개정판(2026-10-20 의료기기법)은 본문에 아직 시행 전인 ⑧이 들어 있어 ⑦까지만 자른다.
        # ⑧이 없는 판은 조문 끝까지. 근본 해결(현행판 본문 받기)은 공용 법령 조회 후속 작업.
        device_misleading=_article(device, 26, " 제7항", "⑦ 누구든지",
                                   "⑧" if "⑧" in article_text(device.body, 26) else None),
        device_exemption=_article(rule, 32, " 제1항", "① 법 제15조제6항", "②"),
        device_notice=notice.ref,
        devices=tuple(parse_device_items(annex_text(notice.body, 1, title="품목"))),
        cosmetic_definition=_article(cosmetics, 2, " 제1호", '1. "화장품"이란', '2. "기능성화장품"'),
        functional_definition=_article(cosmetics, 2, " 제2호", '2. "기능성화장품"이란', "2의2."),
        cosmetic_business=_article(cosmetics, 3, " 제1항~제3항", "① 화장품제조업 또는 화장품책임판매업", "④"),
        cosmetic_business_scope=_article(cosmetics, 2, " 제11호", '11. "화장품책임판매업"이란', "12."),
        functional_review=_article(cosmetics, 4, " 제1항", "① 기능성화장품으로 인정받아", "②"),
        cosmetic_ban=_article(cosmetics, 8, " 제1항", "① 식품의약품안전처장은 화장품의 제조 등에 사용할 수 없는 원료", "②"),
        cosmetic_sale_ban=_article(cosmetics, 15, " 제1호~제5호", "제15조(영업의 금지)", "6. 코뿔소"),
        functional_scope=functional_scope,
        functional_types=tuple(parse_functional_types(functional_scope.text)),
        cosmetic_notice=_article(safety, 3, "", "제3조(사용할 수 없는 원료)"),
        banned=tuple(parse_banned_ingredients(annex_text(safety.body, 1, title="사용할 수 없는 원료"))),
    )
