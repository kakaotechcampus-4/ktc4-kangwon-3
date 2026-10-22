"""규제 Tool이 함께 쓰는 법제처 근거 조회 도구.

- 조회별로 나뉜 법제처 클라이언트(#293) 4개를 한 객체로 묶는다(LawApiClients).
- 기준일에 시행 중인 버전을 고르고(select_version), 받은 본문이 그 문서인지 다시 대조한다(check_body).
- 조문·별표 원문을 꺼내고(article_text, annex_text), 버전을 고정한 공개 열람 주소를 만든다.
- 기준일별로 근거를 캐시한다(CachedLoader).

전기 Tool(#290)에도 같은 역할의 코드가 있다. 전기 Tool 코드는 후속 PR에서 이 모듈로 합친다.
"""

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, Protocol, TypeVar
from xml.etree.ElementTree import ParseError

from pydantic import ValidationError

from ...clients.law import AdmrulSearchClient, AdmrulTextClient, LawSearchClient, LawTextClient
from ...schemas.clients.law_request import LawSearchRequest, LawTextRequest
from ...schemas.clients.law_response import (
    AdmrulSearchResponse, AdmrulTextResponse, LawSearchResponse, LawTextResponse,
)
from ...schemas.schemas import LegalSource

logger = logging.getLogger(__name__)

_BOX_DRAWING = {code: None for code in range(0x2500, 0x2580)}


class EvidenceUnavailable(RuntimeError):
    """조회는 됐지만 필요한 문서·버전·본문을 확인할 수 없다. 조회 실패(네트워크·API 오류)와 구분한다."""


class LawLookupError(RuntimeError):
    """법제처가 유효한 응답을 주지 않았다(API 오류 응답·XML 아님·기본정보 없음·응답 형식 불일치).

    법제처 클라이언트는 이런 경우 RuntimeError를 던진다. 호출 지점에서만 이 예외로 바꿔,
    Tool 내부의 버그(RuntimeError 계열)가 API 실패로 분류되지 않게 한다.
    """


def compact(text: str) -> str:
    """공백과 표 테두리 문자를 지운다. 원문 대조·이름 비교에 쓴다."""
    return "".join((text or "").translate(_BOX_DRAWING).split())


def normalize_text(text: str) -> str:
    """표 테두리 문자를 지우고 공백을 하나로 모은다. 사람이 읽을 원문용."""
    return " ".join((text or "").translate(_BOX_DRAWING).split())


_WORD_END = set(".,)」』]:;·의로와과는은을를에게서며고된한및도면다요")


def join_wrapped(fragments: list[str]) -> str:
    """칸 폭 때문에 여러 줄로 나뉜 칸 글자를 잇는다.

    줄 끝이 문장부호나 흔한 조사·어미로 끝나면 띄어 쓰고, 아니면 단어 중간에서 끊긴 것으로 보고 붙인다
    ("인라인스" + "케이트" → "인라인스케이트", "유아용의" + "의류" → "유아용의 의류"). 표 줄 끝 여백으로는 구분되지 않는다.
    """
    text = ""
    for fragment in (normalize_text(part) for part in fragments):
        if not fragment:
            continue
        if text and (text[-1] in _WORD_END or not ("가" <= text[-1] <= "힣") or not ("가" <= fragment[0] <= "힣")):
            text += " "
        text += fragment
    return text


class LawLookup(Protocol):
    """근거 조회에 필요한 법제처 조회 4가지. 운영은 LawApiClients, 테스트는 Fake를 쓴다."""

    def search_law(self, request: LawSearchRequest) -> LawSearchResponse: ...
    def get_law_text(self, request: LawTextRequest) -> LawTextResponse: ...
    def search_admrul(self, request: LawSearchRequest) -> AdmrulSearchResponse: ...
    def get_admrul_text(self, request: LawTextRequest) -> AdmrulTextResponse: ...


class LawApiClients:
    """조회별로 나뉜 법제처 클라이언트(#293) 4개를 LawLookup 모양으로 묶는다. 다 쓰면 close()로 닫는다.

    Args:
        law_search, law_text, admrul_search, admrul_text: 각 조회 클라이언트(fetch_parsed·close를 가진 객체).
    """

    def __init__(self, law_search, law_text, admrul_search, admrul_text):
        self._law_search = law_search
        self._law_text = law_text
        self._admrul_search = admrul_search
        self._admrul_text = admrul_text

    @classmethod
    def from_oc(cls, oc: str) -> "LawApiClients":
        return cls(LawSearchClient(oc), LawTextClient(oc), AdmrulSearchClient(oc), AdmrulTextClient(oc))

    def search_law(self, request: LawSearchRequest) -> LawSearchResponse:
        return self._law_search.fetch_parsed(request)

    def get_law_text(self, request: LawTextRequest) -> LawTextResponse:
        return self._law_text.fetch_parsed(request)

    def search_admrul(self, request: LawSearchRequest) -> AdmrulSearchResponse:
        return self._admrul_search.fetch_parsed(request)

    def get_admrul_text(self, request: LawTextRequest) -> AdmrulTextResponse:
        return self._admrul_text.fetch_parsed(request)

    def close(self) -> None:
        for client in (self._law_search, self._law_text, self._admrul_search, self._admrul_text):
            client.close()


_R = TypeVar("_R")


def lookup(call: Callable[..., _R], request) -> _R:
    """클라이언트 호출 하나를 실행한다. httpx 오류는 그대로 올려 호출자가 HTTP 상태별로 분류한다."""
    try:
        return call(request)
    except (RuntimeError, ParseError, ValidationError) as exc:
        raise LawLookupError(f"법제처 응답을 확인하지 못했습니다 ({type(exc).__name__}).") from exc


@dataclass(frozen=True)
class DocRef:
    """근거 문서 한 버전의 식별 정보. 본문 없이 캐시·결과에 들고 다닌다."""

    name: str
    document_id: str
    version_id: str
    enforce_date: str
    is_admrul: bool

    @property
    def url(self) -> str:
        """버전을 고정한 공개 열람 주소. 요청 URL(OC 포함)은 쓰지 않는다."""
        if self.is_admrul:
            return f"https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq={self.version_id}"
        return f"https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq={self.version_id}"

    def source(self, article: str, quoted_text: str) -> LegalSource:
        return LegalSource(
            source_name="법제처 국가법령정보", law_name=self.name, article=article,
            quoted_text=quoted_text, source_url=self.url, effective_date=self.enforce_date, is_mock=False,
        )

    def describe(self) -> dict[str, str]:
        return {"name": self.name, "document_id": self.document_id, "version_id": self.version_id,
                "enforce_date": self.enforce_date, "url": self.url}


@dataclass(frozen=True)
class LawDocument:
    """기준일에 고른 문서 한 버전과 본문."""

    name: str
    document_id: str
    version_id: str
    enforce_date: str
    body: LawTextResponse | AdmrulTextResponse
    is_admrul: bool

    @property
    def ref(self) -> DocRef:
        return DocRef(self.name, self.document_id, self.version_id, self.enforce_date, self.is_admrul)


def _day(value: str | None) -> date:
    try:
        return datetime.strptime(value or "", "%Y%m%d").date()
    except ValueError as exc:
        raise EvidenceUnavailable("시행일 형식이 잘못됐습니다.") from exc


def select_version(result, *, name: str, identifier: str, id_field: str, name_field: str,
                   version_field: str, as_of: date):
    """검색 결과에서 기준일에 시행 중인 버전을 고른다.

    문서 ID와 이름이 정확히 일치하는 항목 중 시행일이 기준일 이하인 최신 버전을 쓴다.
    검색 첫 행·미래 시행 버전에 의존하지 않으며, 판단할 수 없으면 임의로 고르지 않는다.

    Raises:
        EvidenceUnavailable: 목록 불완전, 후보 없음, 같은 시행일에 버전이 둘 이상, 버전 번호 이상.
    """
    if result.total_count != len(result.items):
        raise EvidenceUnavailable("검색 목록이 불완전합니다.")
    candidates = []
    for item in result.items:
        if getattr(item, id_field) != identifier or compact(getattr(item, name_field) or "") != compact(name):
            continue
        enforced = _day(item.enforce_date)
        if enforced <= as_of:
            candidates.append((enforced, item))
    if not candidates:
        raise EvidenceUnavailable(f"기준일에 적용할 '{name}' 버전을 찾지 못했습니다.")
    latest_day = max(day for day, _ in candidates)
    latest = [item for day, item in candidates if day == latest_day]
    if len({getattr(item, version_field) for item in latest}) != 1:
        raise EvidenceUnavailable(f"'{name}'의 같은 시행일 버전이 모호합니다.")
    selected = latest[0]
    if not re.fullmatch(r"[0-9]+", getattr(selected, version_field) or ""):
        raise EvidenceUnavailable("문서 일련번호가 잘못됐습니다.")
    return selected


def check_body(body, *, name: str, identifier: str, enforce_date: str) -> None:
    """본문이 검색에서 고른 문서인지 대조한다(번호가 틀려도 법제처는 다른 문서를 정상 응답한다).

    본문 시행일은 대조하지 않고 다르면 기록만 남긴다. 버전은 검색에서 고른 일련번호로 요청해 정해지고,
    시행일이 나뉜 개정판은 검색과 본문의 시행일이 다르게 온다(예: 의료기기법 일련번호 291321, 검색 20261020
    현행, 본문 20271021 — 부칙에 따라 일부 조문이 나중에 시행). 근거 시행일은 검색 값(기준일에 시행 중인 판)을 쓴다.
    """
    if body.document_id != identifier or compact(body.name or "") != compact(name):
        raise EvidenceUnavailable(f"'{name}' 검색 문서와 본문 식별 정보가 다릅니다.")
    if body.enforce_date != enforce_date:
        logger.info("'%s' 검색 시행일 %s와 본문 시행일 %s가 다름 (시행일이 나뉜 개정판)", name, enforce_date, body.enforce_date)


def load_law(client: LawLookup, *, name: str, law_id: str, as_of: date) -> LawDocument:
    """법령(법률·시행령·시행규칙)을 기준일 버전으로 받는다."""
    selected = select_version(
        lookup(client.search_law, LawSearchRequest(query=name, display=100)),
        name=name, identifier=law_id, id_field="law_id", name_field="law_name", version_field="mst", as_of=as_of,
    )
    body = lookup(client.get_law_text, LawTextRequest(mst=selected.mst))
    check_body(body, name=name, identifier=law_id, enforce_date=selected.enforce_date)
    return LawDocument(name, law_id, selected.mst, selected.enforce_date, body, is_admrul=False)


def load_admrul(client: LawLookup, *, name: str, rule_id: str, as_of: date) -> LawDocument:
    """행정규칙(고시·훈령·예규)을 기준일 버전으로 받는다."""
    selected = select_version(
        lookup(client.search_admrul, LawSearchRequest(query=name, display=100)),
        name=name, identifier=rule_id, id_field="rule_id", name_field="name", version_field="serial_number",
        as_of=as_of,
    )
    body = lookup(client.get_admrul_text, LawTextRequest(mst=selected.serial_number))
    check_body(body, name=name, identifier=rule_id, enforce_date=selected.enforce_date)
    return LawDocument(name, rule_id, selected.serial_number, selected.enforce_date, body, is_admrul=True)


def article_text(body, number: int) -> str:
    """조문 하나의 전문을 원문 순서로 모은다. 항 아래 호·목이 중첩된 응답과 평평한 응답 모두 처리한다.

    Raises:
        EvidenceUnavailable: 조문을 유일하게 찾지 못한 경우.
    """
    articles = [article for article in body.articles
                if str(article.article_number or "").lstrip("0") == str(number)
                and article.article_branch_number in (None, "", "0", "00")]
    if not articles:
        articles = [article for article in body.articles
                    if (article.article_content or "").lstrip().startswith(f"제{number}조(")]
    if len(articles) != 1:
        raise EvidenceUnavailable(f"제{number}조를 유일하게 식별하지 못했습니다.")
    parts = [articles[0].article_content or ""]

    def collect(node) -> None:
        parts.append(getattr(node, "content", None) or "")
        for child_field in ("items", "sub_items"):
            for child in getattr(node, child_field, None) or []:
                collect(child)

    for node in articles[0].paragraphs or []:
        collect(node)
    return normalize_text(" ".join(parts))


def annex_text(body, number: int, *, branch: int = 0, title: str | None = None) -> str:
    """별표 하나의 원문(표 테두리 포함)을 꺼낸다. 표 파싱은 호출자가 한다.

    Raises:
        EvidenceUnavailable: 별표를 유일하게 찾지 못했거나 본문이 비어 있는 경우.
    """
    wanted_branch = (None, "", "00") if branch == 0 else (f"{branch:02d}",)
    matches = [annex for annex in body.annexes
               if annex.annex_type == "별표" and annex.annex_number == f"{number:04d}"
               and annex.annex_branch_number in wanted_branch
               and (title is None or compact(title) in compact(annex.annex_title or ""))]
    label = f"별표 {number}" + (f"의{branch}" if branch else "")
    if len(matches) != 1 or not (matches[0].annex_content or "").strip():
        raise EvidenceUnavailable(f"{label}의 본문을 확인하지 못했습니다.")
    return matches[0].annex_content


_T = TypeVar("_T")


class CachedLoader(Generic[_T]):
    """기준일별로 근거를 캐시한다. 여러 요청이 동시에 와도 한 번만 조회한다.

    법령은 하루에도 개정·시행될 수 있으므로 기준일을 키로 쓰고, ttl_seconds가 지나면 다시 조회한다.
    실패는 캐시하지 않는다.
    """

    def __init__(self, load: Callable[[date], _T], *, ttl_seconds: float = 6 * 3600,
                 clock: Callable[[], float] = time.monotonic):
        self._load = load
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[date, tuple[float, _T]] = {}
        self.loads = 0

    def load(self, as_of: date) -> _T:
        with self._lock:
            cached = self._cache.get(as_of)
            if cached is not None and self._clock() - cached[0] < self._ttl:
                return cached[1]
            value = self._load(as_of)
            self.loads += 1
            self._cache = {as_of: (self._clock(), value)}
            return value
