from datetime import datetime

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.api_response_cache import ApiResponseCache


class ApiResponseCacheRepository:
    """외부 API 응답 캐시 Repository. 트랜잭션(commit)은 호출부 책임.

    PK가 (client, request_key) 두 칸이라 BaseRepository를 상속하지 않는다.

    Attributes:
        session: SQLAlchemy DB 세션.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, client: str, request_key: str) -> ApiResponseCache | None:
        """캐시 한 건을 조회한다. 만료 여부는 호출부가 판단한다.

        Args:
            client: 클라이언트 이름(예: "law.text").
            request_key: 요청 해시.

        Returns:
            ApiResponseCache | None: 캐시 행. 없으면 None. 만료된 행도 그대로 돌려준다.
        """
        return self.session.get(ApiResponseCache, (client, request_key))

    def put(self, entry: ApiResponseCache) -> None:
        """캐시 한 건을 저장한다. 같은 키가 있으면 응답과 수집 시각을 덮어쓴다.

        Args:
            entry: 저장할 캐시 행.
        """
        values = {
            "client": entry.client,
            "request_key": entry.request_key,
            "request": entry.request,
            "response": entry.response,
            "expires_at": entry.expires_at,
        }
        stmt = insert(ApiResponseCache).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ApiResponseCache.client, ApiResponseCache.request_key],
            set_={
                **{key: stmt.excluded[key] for key in values if key not in ("client", "request_key")},
                "fetched_at": func.now(),
            },
        )
        self.session.execute(stmt)

    def delete_expired(self, now: datetime) -> int:
        """만료된 캐시 행을 지운다. 영구 보관 행(expires_at 없음)은 남긴다.

        Args:
            now: 기준 시각. expires_at이 이보다 이른 행을 지운다.

        Returns:
            int: 지운 행 수.
        """
        stmt = delete(ApiResponseCache).where(ApiResponseCache.expires_at < now)
        return self.session.execute(stmt).rowcount
