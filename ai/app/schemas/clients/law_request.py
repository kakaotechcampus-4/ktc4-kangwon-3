"""법제처 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel, Field


class LawSearchRequest(BaseModel):
    """법령 검색 요청.

    Args:
        query: 법령명 검색어 (예: "전파법", "약사법").
        display: 검색 결과 건수. 기본 20.
    """

    query: str = Field(min_length=1)
    display: int = Field(default=20, ge=1, le=100)


class LawTextRequest(BaseModel):
    """법령 본문 조회 요청.

    Args:
        mst: 법령일련번호. 법령검색 응답의 법령일련번호를 넣는다.
    """

    mst: str = Field(min_length=1)


class LicbylTextRequest(BaseModel):
    """별표·서식 본문 조회 요청. search_licbyl() 결과 항목의 값을 그대로 넣는다.

    Args:
        related_law_mst: 별표가 속한 관련 법령 일련번호 (검색 결과의 related_law_mst).
        table_number: 별표번호 6자리 = 별표번호 4자리 + 가지번호 2자리 (예: "000300" → 별표 0003, 가지 00).
        table_type: 별표종류 (예: "별표", "서식"). 한 법령 안에 같은 번호의 별표와 서식이 따로 있어 번호만으로는 구분할 수 없다.
    """

    related_law_mst: str = Field(min_length=1)
    table_number: str = Field(pattern=r"^\d{6}$")
    table_type: str = Field(min_length=1)
