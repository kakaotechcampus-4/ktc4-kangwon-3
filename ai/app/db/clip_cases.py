"""CLIP 품목분류 결정사례 DB 조회 객체. hs_cases(clip-ingest로 적재)에서 비슷한 사례·같은 HS 사례를 찾는다.

결과는 CLIP 클라이언트와 같은 CLIPCase라 Tool은 받은 사례를 다루는 로직을 바꾸지 않는다.
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from ..schemas.clients.customs_response import CLIPCase
from .models.hs_case import HsCase
from .repositories.hs_case import HsCaseRepository


def _to_case(row: HsCase) -> CLIPCase:
    return CLIPCase(**{name: getattr(row, name) for name in CLIPCase.model_fields})


class ClipCaseDatabase:
    """hs_cases에서 결정사례를 찾는다.

    Args:
        session_factory: DB 세션을 만드는 함수.
        embed_query: 검색어 → 벡터 (clients.llm.embedding.embed_text_sync). 적재 때와 같은 모델이어야 한다.
        embedding_model: embed_query가 쓰는 임베딩 모델 이름. 같은 모델로 만든 행만 본다.
    """

    def __init__(self, session_factory: Callable[[], Session], *, embed_query: Callable[[str], list[float]],
                 embedding_model: str):
        self._session_factory = session_factory
        self._embed_query = embed_query
        self._embedding_model = embedding_model

    def search_similar(self, text: str, *, top_k: int = 10) -> list[tuple[CLIPCase, float]]:
        """글과 의미가 비슷한 결정사례를 찾는다.

        Args:
            text: 상품명·판매글 등 검색할 글.
            top_k: 최대 결과 수.

        Returns:
            list[tuple[CLIPCase, float]]: (결정사례, 코사인 거리). 거리가 작을수록 비슷함.
        """
        vector = self._embed_query(text)
        with self._session_factory() as session:
            rows = HsCaseRepository(session).search_by_vector(
                vector, embedding_model=self._embedding_model, top_k=top_k)
            return [(_to_case(row), distance) for row, distance in rows]

    def find_by_hs_code(self, hs_code: str) -> list[CLIPCase]:
        """HS 코드가 겹치는 결정사례를 찾는다. 6자리면 그 아래 10자리 사례까지 나온다.

        Args:
            hs_code: HS 코드(숫자만).

        Returns:
            list[CLIPCase]: 결정사례.
        """
        with self._session_factory() as session:
            return [_to_case(row) for row in HsCaseRepository(session).get_by_hs_code(hs_code)]
