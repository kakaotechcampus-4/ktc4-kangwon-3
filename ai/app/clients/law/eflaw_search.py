"""법제처 시행법령 검색 클라이언트.

역할
    법령명 검색어로 시행일 기준 법령 목록(연혁 포함)을 조회.
    특정 시점에 시행 중이던 버전의 법령일련번호(MST)를 찾을 때 사용. 응답 형식은 법령 검색과 같음.
"""

from .law_search import LawSearchClient


class EflawSearchClient(LawSearchClient):
    """시행법령 검색(target=eflaw) 클라이언트. 파싱은 법령 검색과 같음."""

    _TARGET = "eflaw"
