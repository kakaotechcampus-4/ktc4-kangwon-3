"""법제처 시행법령 검색 클라이언트.

역할
    법령명 검색어로 시행일 기준 법령 목록(연혁 포함)을 조회.
    특정 시점에 시행 중이던 버전의 법령일련번호(MST)를 찾을 때 사용. 응답 형식은 법령 검색과 같음.
"""

from .law_search import LawSearchClient

# 현행연혁 조건(nw): 1 연혁, 2 시행예정, 3 현행
_CURRENT_AND_UPCOMING = "2,3"


class EflawSearchClient(LawSearchClient):
    """시행법령 검색(target=eflaw) 클라이언트. 파싱은 법령 검색과 같음.

    Args:
        oc: 법제처 OC.
        include_history: False면 현행·시행예정 버전만 받음. 연혁이 많아 한 번에 100건을 넘는 법령
            (식품위생법 411건, 관세법 1,754건)도 잘리지 않음. 기준일이 현행 시행일보다 이르면 고를 버전이 없음.
    """

    _TARGET = "eflaw"

    def __init__(self, oc: str, *, include_history: bool = True):
        super().__init__(oc)
        self._include_history = include_history

    def _extra_params(self) -> dict[str, str]:
        return {} if self._include_history else {"nw": _CURRENT_AND_UPCOMING}
