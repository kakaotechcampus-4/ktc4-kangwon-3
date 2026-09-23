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

class LawArticleSubItem(BaseModel):
    """항·호·목 하위 항목."""

    number: str | None = None
    content: str | None = None


class LawArticle(BaseModel):
    """법령 조문 단건."""

    article_number: str | None = None
    article_branch_number: str | None = None
    article_is_exist: str | None = None
    article_title: str | None = None
    article_content: str | None = None
    paragraphs: list[LawArticleSubItem] = []
    items: list[LawArticleSubItem] = []
    sub_items: list[LawArticleSubItem] = []
    enforce_date: str | None = None
    reference: str | None = None


class LawTextResponse(BaseModel):
    """법령 본문 조회 응답.

    Attributes:
        articles: 조문 목록.
    """

    articles: list[LawArticle]
