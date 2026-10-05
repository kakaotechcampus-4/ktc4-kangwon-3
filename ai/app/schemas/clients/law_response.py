"""법제처 외부 API 응답 모델."""

from pydantic import BaseModel


# -- 법령검색 (law, eflaw 공용) --

class LawSearchItem(BaseModel):
    """법령/시행법령 검색 결과 단건."""

    mst: str | None = None
    law_id: str | None = None
    law_name: str | None = None
    law_name_abbr: str | None = None
    law_type: str | None = None
    promulgate_date: str | None = None
    promulgate_number: str | None = None
    enforce_date: str | None = None
    revision_type: str | None = None
    department: str | None = None


class LawSearchResponse(BaseModel):
    """법령/시행법령 검색 응답.

    Attributes:
        total_count: 전체 검색 건수.
        items: 검색 결과 목록.
    """

    total_count: int
    items: list[LawSearchItem]


# -- 행정규칙 검색 (admrul) --

class AdmrulSearchItem(BaseModel):
    """행정규칙 검색 결과 단건."""

    serial_number: str | None = None
    name: str | None = None
    rule_type: str | None = None
    issue_date: str | None = None
    issue_number: str | None = None
    department: str | None = None
    enforce_date: str | None = None
    revision_type: str | None = None
    rule_id: str | None = None


class AdmrulSearchResponse(BaseModel):
    """행정규칙 검색 응답.

    Attributes:
        total_count: 전체 검색 건수.
        items: 검색 결과 목록.
    """

    total_count: int
    items: list[AdmrulSearchItem]


# -- 자치법규(별표서식) 검색 (licbyl) --

class LicbylSearchItem(BaseModel):
    """자치법규(별표서식) 검색 결과 단건."""

    serial_number: str | None = None
    related_law_mst: str | None = None
    related_law_id: str | None = None
    name: str | None = None
    related_law_name: str | None = None
    table_number: str | None = None
    table_type: str | None = None
    department: str | None = None
    promulgate_date: str | None = None
    promulgate_number: str | None = None
    revision_type: str | None = None
    law_type: str | None = None


class LicbylSearchResponse(BaseModel):
    """자치법규(별표서식) 검색 응답.

    Attributes:
        total_count: 전체 검색 건수.
        items: 검색 결과 목록.
    """

    total_count: int
    items: list[LicbylSearchItem]


# -- 법령본문 --

class LawSubItem(BaseModel):
    """목 단건. 내용에 번호 포함 (예: "가. 정격")."""

    number: str | None = None
    content: str | None = None


class LawItem(BaseModel):
    """호 단건. 내용에 번호 포함 (예: "1. 법인의 정관")."""

    number: str | None = None
    content: str | None = None
    sub_items: list[LawSubItem] = []


class LawParagraph(BaseModel):
    """항 단건. 항번호 없이 호만 있는 항은 number·content가 None."""

    number: str | None = None
    content: str | None = None
    items: list[LawItem] = []


class LawArticle(BaseModel):
    """법령 조문 단건. 항 → 호 → 목 순서로 중첩."""

    article_number: str | None = None
    article_branch_number: str | None = None
    article_is_exist: str | None = None
    article_title: str | None = None
    article_content: str | None = None
    paragraphs: list[LawParagraph] = []
    enforce_date: str | None = None
    reference: str | None = None


class LawAnnex(BaseModel):
    """법령 별표 단건.

    Attributes:
        annex_number: 별표번호 (예: "0003").
        annex_branch_number: 별표가지번호 (예: "00").
        annex_type: 별표구분. "별표"(품목표·기준표)와 "서식"(신청서 등)을 구분한다.
        annex_title: 별표제목.
        annex_content: 별표내용 원문.
    """

    annex_number: str | None = None
    annex_branch_number: str | None = None
    annex_type: str | None = None
    annex_title: str | None = None
    annex_content: str | None = None


class LawTextResponse(BaseModel):
    """법령 본문 조회 응답.

    기본정보(name, document_id 등)는 요청한 문서를 받았는지 검색 결과와 대조하는 데 쓴다.
    법령ID를 MST 자리에 넣는 등 번호가 틀려도 법제처는 다른 법의 정상 본문을 돌려주기 때문이다.

    Attributes:
        name: 법령명 (admrul은 행정규칙명).
        document_id: 법령ID (admrul은 행정규칙ID). 검색 결과의 law_id / rule_id와 대조한다.
        enforce_date: 시행일자 (YYYYMMDD).
        department: 소관부처명.
        articles: 조문 목록.
        annexes: 별표 목록. 별표가 없는 문서는 빈 목록.
    """

    name: str | None = None
    document_id: str | None = None
    enforce_date: str | None = None
    department: str | None = None
    articles: list[LawArticle]
    annexes: list[LawAnnex] = []
