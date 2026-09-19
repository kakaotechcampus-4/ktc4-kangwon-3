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
