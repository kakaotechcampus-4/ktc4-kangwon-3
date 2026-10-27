"""통관 요건 근거(관세법 제226조, 세관장확인 고시, 대외무역법 시행령 제19조)를 조회하고 읽는다.

- 관세법 제226조: 수입할 때 다른 법령의 허가·승인·표시 등 조건을 세관장에게 증명해야 하는 근거.
- 세관장확인물품 및 확인방법 지정고시
  - 별표 2: 세관장확인 대상 수입물품의 대상 법령과 구비요건(법령 단위). HS별 대응은 세관장확인 GW가 준다.
  - 제7조 제2항: 세관장확인을 생략할 수 있는 물품(대외무역법 시행령 제19조 사유)과 생략하지 않는 법령(단서 목록).
- 대외무역법 시행령 제19조: 수출입승인 면제 사유(상행위 이외 목적 등). 구매대행 안내의 근거로 함께 붙인다.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from ..common.law import (
    DocRef, EvidenceUnavailable, LawLookup, article_text, compact, join_wrapped, load_admrul, load_law,
)

ACT_NAME = "관세법"
ACT_ID = "001556"
DECREE_NAME = "대외무역법 시행령"
DECREE_ID = "003313"
NOTICE_NAME = "관세법 제226조에 따른 세관장확인물품 및 확인방법 지정고시"
NOTICE_ID = "35531"

_DOTS = str.maketrans("", "", "·ㆍ?・")
_ROW_NUMBER_RE = re.compile(r"^\((\d+)\)")
_LAW_NAME_RE = re.compile(r"「([^」]+)」")
# 괄호 한 겹(안에 괄호가 한 번 더 있어도 된다). 단서의 조건 부분을 가리는 데 쓴다.
_PAREN_RE = re.compile(r"\((?:[^()]|\([^()]*\))*\)")
# 목 번호(가. 나. … 하. 거. 너. …). 앞이 공백이거나 문장 시작일 때만 번호로 본다("한다. 다만"의 "다."는 아니다).
_ITEM_LABEL_RE = re.compile(r"(?:^|\s)[가-힣]\.\s")


def law_key(name: str) -> str:
    """법령 이름 비교용 키. 공백·가운뎃점(·, ㆍ, 깨진 ?) 차이를 무시한다(고시는 'ㆍ', GW는 '·'를 쓴다).

    GW는 같은 법령에 요건 종류를 덧붙여 줄 때가 있어(예: "야생생물 보호 및 관리에 관한 법률(허가)") 끝의 괄호는 뗀다.

    Args:
        name: 법령 이름.

    Returns:
        str: 비교용 키.
    """
    return compact(re.sub(r"\([^()]*\)\s*$", "", name)).translate(_DOTS)


@dataclass(frozen=True)
class ConfirmationRow:
    """고시 별표 2의 대상 법령 한 행.

    Attributes:
        number: 별표의 행 번호. 예: 9.
        law_name: 대상 법령 이름. 예: "전기용품 및 생활용품 안전 관리법".
        scope: 대상 법령 및 물품의 범위 칸 원문(하위 (가)(나) 포함).
        requirements: 구비요건 칸 원문.
    """

    number: int
    law_name: str
    scope: str
    requirements: str

    @property
    def text(self) -> str:
        """근거 인용에 쓸 행 한 줄.

        Returns:
            str: "(번호) 범위 — 구비요건: …" 모양의 글.
        """
        return f"({self.number}) {self.scope.removeprefix(f'({self.number})').strip()} — 구비요건: {self.requirements}"


@dataclass(frozen=True)
class CustomsEvidence:
    """한 기준일에 적용할 통관 근거 묶음."""

    act: DocRef
    act_article: str
    notice: DocRef
    notice_article: str
    decree: DocRef
    decree_article: str
    rows: tuple[ConfirmationRow, ...]
    # 고시 제7조 제2항 제1호 단서: 대외무역법 시행령 제19조 사유여도 세관장확인을 생략하지 않는 법령.
    # 키는 law_key, 값은 그 법령 뒤에 붙은 조건 원문(예: "(금지물질, 제한물질에 한함 …)"). 조건이 없으면 "".
    # 단서를 읽지 못하면 None이다. 이때 구매대행 생략 여부는 "확인 필요"로 안내한다(근거 묶음 전체는 그대로 쓴다).
    omission_exceptions: dict[str, str] | None = field(default_factory=dict)

    def row_for(self, law_name: str) -> ConfirmationRow | None:
        """법령 이름으로 별표 2 행을 찾는다.

        Args:
            law_name: 법령 이름 (GW 표기도 됨).

        Returns:
            ConfirmationRow | None: 찾은 행. 없으면 None.
        """
        key = law_key(law_name)
        return next((row for row in self.rows if law_key(row.law_name) == key), None)

    def documents(self) -> list[dict[str, str]]:
        """결과 query에 남길 문서 식별 정보.

        Returns:
            list[dict[str, str]]: 관세법·고시·대외무역법 시행령 순.
        """
        return [ref.describe() for ref in (self.act, self.notice, self.decree)]


def parse_confirmation_rows(text: str) -> list[ConfirmationRow]:
    """고시 별표 2(세관장확인대상 수입물품)의 표를 대상 법령 행으로 나눈다.

    표는 '대상법령 및 물품의 범위 │ 구비요건' 두 칸이고, ├ 줄이 행 경계다. 삭제된 행과 머리글은 넣지 않는다.

    Args:
        text: 고시 별표 2 원문.

    Returns:
        list[ConfirmationRow]: 대상 법령 행.

    Raises:
        EvidenceUnavailable: 행을 찾지 못한 경우.
    """
    rows: list[ConfirmationRow] = []
    left: list[str] = []
    right: list[str] = []

    def flush() -> None:
        scope, requirements = join_wrapped(left), join_wrapped(right)
        left.clear()
        right.clear()
        number = _ROW_NUMBER_RE.match(scope)
        name = _LAW_NAME_RE.search(scope)
        if number is None or name is None or "삭제" in compact(scope)[:12]:
            return
        rows.append(ConfirmationRow(int(number.group(1)), name.group(1).strip(), scope, requirements))

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("├", "┌", "└")):
            flush()
            continue
        if not stripped.startswith("│"):
            continue
        cells = stripped.split("│")
        if len(cells) < 3 or "대상법령및물품의범위" in compact(cells[1]):
            continue
        left.append(cells[1])
        right.append(cells[2])
    flush()
    if not rows:
        raise EvidenceUnavailable("세관장확인 고시 별표 2에서 대상 법령을 찾지 못했습니다.")
    return rows


def parse_omission_exceptions(article: str) -> dict[str, str]:
    """고시 제7조 제2항 제1호 단서의 법령 목록(세관장확인을 생략하지 않는 법령)을 읽는다.

    Args:
        article: 고시 제7조 원문.

    Returns:
        dict[str, str]: law_key → 법령 뒤에 붙은 조건 원문. 예: {"화학물질관리법": "(금지물질, 제한물질에 한함. …)"}.

    Raises:
        EvidenceUnavailable: 단서 목록을 찾지 못한 경우.
    """
    # 단서 목록은 제1호 단서부터 제2호 시작 전까지다. 제2호 문구가 개정으로 바뀌어도 읽히도록 "2. "만 본다.
    found = re.search(r"다만, 다음 각 목의 법령을 적용받는 물품은.*?확인한다\.(.*?)(?:\s2\.\s|③|$)", article)
    if found is None:
        raise EvidenceUnavailable("세관장확인 고시 제7조의 생략 제외 법령 목록을 찾지 못했습니다.")
    exceptions: dict[str, str] = {}
    for item in _ITEM_LABEL_RE.split(found.group(1)):
        # 괄호 안(조건)의 「」는 다른 고시 이름이라 법령으로 보지 않는다. 괄호 밖의 「」는 모두 법령이다(한 목에 둘 이상일 수 있다).
        outside = _PAREN_RE.sub(lambda match: " " * len(match.group(0)), item)
        names = list(_LAW_NAME_RE.finditer(outside))
        if not names:
            continue
        condition = item[names[-1].end():].strip()
        for name in names:
            exceptions[law_key(name.group(1))] = condition
    if not exceptions:
        raise EvidenceUnavailable("세관장확인 고시 제7조의 생략 제외 법령 목록이 비어 있습니다.")
    return exceptions


def load_customs_evidence(client: LawLookup, as_of: date) -> CustomsEvidence:
    """법제처에서 관세법·고시·대외무역법 시행령을 기준일 버전으로 받아 근거를 만든다.

    Args:
        client: 법제처 조회.
        as_of: 기준일.

    Returns:
        CustomsEvidence: 기준일 근거 묶음.

    Raises:
        EvidenceUnavailable: 문서·버전·조문·별표를 확인할 수 없는 경우.
        LawLookupError, httpx.HTTPError: 조회 자체가 실패한 경우.
    """
    act = load_law(client, name=ACT_NAME, law_id=ACT_ID, as_of=as_of)
    decree = load_law(client, name=DECREE_NAME, law_id=DECREE_ID, as_of=as_of)
    notice = load_admrul(client, name=NOTICE_NAME, rule_id=NOTICE_ID, as_of=as_of)
    act_article = article_text(act.body, 226)
    decree_article = article_text(decree.body, 19)
    notice_article = article_text(notice.body, 7)
    # 판단에 쓰는 문구가 실제로 있는지 확인한다(빈 본문·다른 조문 방어).
    if "세관장" not in act_article or "상행위" not in decree_article or "생략" not in notice_article:
        raise EvidenceUnavailable("통관 근거 조문의 내용을 확인하지 못했습니다.")
    annexes = [annex for annex in notice.body.annexes
               if annex.annex_type == "별표" and annex.annex_number == "0002"
               and annex.annex_branch_number in (None, "", "00")]
    if len(annexes) != 1 or not (annexes[0].annex_content or "").strip():
        raise EvidenceUnavailable("세관장확인 고시 별표 2의 본문을 확인하지 못했습니다.")
    return CustomsEvidence(
        act=act.ref, act_article=act_article, notice=notice.ref, notice_article=notice_article,
        decree=decree.ref, decree_article=decree_article,
        rows=tuple(parse_confirmation_rows(annexes[0].annex_content)),
        omission_exceptions=_omission_or_none(notice_article),
    )


def _omission_or_none(article: str) -> dict[str, str] | None:
    """단서 목록을 읽지 못해도 관세법·별표 2 근거는 쓸 수 있게 None으로 돌려준다.

    Args:
        article: 고시 제7조 원문.

    Returns:
        dict[str, str] | None: 단서 법령 목록. 읽지 못하면 None.
    """
    try:
        return parse_omission_exceptions(article)
    except EvidenceUnavailable:
        return None
