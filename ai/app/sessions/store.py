"""진단 세션을 상품 단위로 메모리에 보관하는 저장소.

보관·교체만 하고 상태를 어떻게 바꿀지는 전이표(transitions)가 정함.
여러 스레드가 함께 쓰므로 모든 읽기·쓰기는 잠금 안에서 처리.
보관소(DB)를 주면 재시작 때 되살릴 세션(성격표의 archived)을 같이 기록함 (#565). 없으면 재시작 때 사라짐.
"""

from collections import Counter
from collections.abc import Callable, Collection
from datetime import datetime, timedelta
from threading import Lock
from typing import Protocol

from ..config import AWAITING_INPUT_RETENTION_SECONDS, SESSION_RETENTION_SECONDS
from ..domain.context import ExecutionContext, RunType
from ..schemas.base import utc_now
from ..schemas.session import DiagnosisSession, SessionStatus
from .transitions import STATUS_TRAITS, Retention, Transition


class SessionArchive(Protocol):
    """재시작 때 되살릴 세션의 보관소. 실패는 보관소가 경고로 남기고 삼킴 (진단은 메모리로 계속)."""

    def save(self, session: DiagnosisSession) -> None:
        """세션을 저장한다. 같은 상품이 있으면 덮어씀."""
        ...

    def remove(self, product_ids: Collection[str]) -> None:
        """세션들을 지운다."""
        ...


class SessionStore:
    """상품 ID를 세션 ID로 쓰는 진단 세션 저장소."""

    def __init__(
        self,
        *,
        retention: timedelta = timedelta(seconds=SESSION_RETENTION_SECONDS),
        awaiting_retention: timedelta = timedelta(seconds=AWAITING_INPUT_RETENTION_SECONDS),
        clock: Callable[[], datetime] = utc_now,
        archive: SessionArchive | None = None,
    ) -> None:
        """저장소를 만든다.

        Args:
            retention: 종료된 세션 보관 시간.
            awaiting_retention: 답변 대기 세션 보관 시간. 지나면 지워져 재진단은 세션 없음(404).
            clock: 현재 시각 함수. 테스트에서 시각을 고정할 때 주입.
            archive: 재시작 때 되살릴 세션의 보관소. None이면 메모리에만 둠.
        """
        self._sessions: dict[str, DiagnosisSession] = {}
        self._lock = Lock()
        # 성격표의 보관 시간 종류 → 보관 시간
        self._retention: dict[Retention, timedelta] = {"ended": retention, "awaiting_input": awaiting_retention}
        self._clock = clock
        self._archive = archive

    def add(self, sessions: list[DiagnosisSession]) -> None:
        """새 세션들을 넣는다. 같은 상품의 세션이 있으면 교체.

        실행 중인 상품인지 확인은 부르는 쪽(세션 관리자) 몫.

        Args:
            sessions: 넣을 세션.
        """
        with self._lock:
            for session in sessions:
                previous = self._sessions.get(session.context.product_id)
                self._sessions[session.context.product_id] = session
                self._archive_change(previous, session)

    def get(self, product_id: str) -> DiagnosisSession | None:
        """세션을 조회한다.

        Args:
            product_id: 세션 ID (상품 ID).

        Returns:
            DiagnosisSession | None: 세션. 없거나 정리됐으면 None.
        """
        with self._lock:
            return self._sessions.get(product_id)

    def count_by_status(self) -> dict[SessionStatus, int]:
        """상태별 보관 중인 세션 수.

        Returns:
            dict[SessionStatus, int]: 모든 상태를 0 포함해 담음.
        """
        with self._lock:
            counts = Counter(session.status for session in self._sessions.values())
        return {status: counts[status] for status in SessionStatus}

    def unfinished(self) -> list[DiagnosisSession]:
        """시간 초과 대상(성격표의 times_out) 세션 목록. 답변 대기는 실행이 끝난 상태라 제외.

        Returns:
            list[DiagnosisSession]: 접수 또는 실행 중인 세션.
        """
        with self._lock:
            return [session for session in self._sessions.values() if STATUS_TRAITS[session.status].times_out]

    def replace(
        self, context: ExecutionContext, change: Callable[[DiagnosisSession], Transition],
    ) -> Transition | None:
        """같은 실행(run_id)의 세션에 change를 적용하고 나온 세션으로 교체한다. 재접수면 새 실행의 세션이 들어감.

        읽기부터 교체까지 잠금 하나로 묶음. 그 사이 다른 스레드의 변경이 끼어들지 않음.

        Args:
            context: 이 실행의 컨텍스트. 세션의 run_id와 같을 때만 바꿈.
            change: 지금 세션을 받아 전이 결과를 돌려주는 함수.

        Returns:
            Transition | None: 전이 결과. 세션이 없거나 재접수로 다른 실행의 세션이면 None.

        Raises:
            Exception: change가 낸 예외 (InvalidTransitionError 등). 세션은 그대로.
        """
        with self._lock:
            session = self._sessions.get(context.product_id)
            # 시간 초과 뒤 재접수되면 같은 상품에 새 세션이 생김. 옛 실행의 늦은 갱신은 무시
            if session is None or session.context.run_id != context.run_id:
                return None
            transition = change(session)
            self._sessions[context.product_id] = transition.session
            self._archive_change(session, transition.session)
            return transition

    def purge(self) -> int:
        """보관 시간이 지난 세션을 성격표의 보관 시간 종류대로 지운다. 접수·실행 중 세션은 시간 초과 처리가 맡음.

        보관 시간은 마지막 상태 변경(updated_at)부터. 답변 대기는 질문을 보낸 시각부터.

        Returns:
            int: 지운 세션 수.
        """
        with self._lock:
            now = self._clock()
            expired = [
                product_id for product_id, session in self._sessions.items()
                if (retention := STATUS_TRAITS[session.status].retention) is not None
                and session.updated_at <= now - self._retention[retention]
            ]
            archived = [product_id for product_id in expired if self._archived(self._sessions[product_id])]
            for product_id in expired:
                del self._sessions[product_id]
            if self._archive is not None and archived:
                self._archive.remove(archived)
            return len(expired)

    def _archive_change(self, previous: DiagnosisSession | None, session: DiagnosisSession) -> None:
        """바뀐 세션을 보관소에 반영한다. 순서가 뒤바뀌지 않게 잠금 안에서 부름.

        단계·Tool 진행처럼 상태가 그대로인 변경은 기록하지 않음 (복원엔 상태 전이만 필요).

        Args:
            previous: 바뀌기 전 세션. 새 상품이면 None.
            session: 바뀐 세션.
        """
        if self._archive is None:
            return
        if self._archived(session):
            same_state = (previous is not None and previous.status is session.status
                          and previous.context.run_id == session.context.run_id)
            if not same_state:
                self._archive.save(session)
        elif previous is not None and self._archived(previous):
            self._archive.remove([session.context.product_id])

    @staticmethod
    def _archived(session: DiagnosisSession) -> bool:
        """보관 대상인지. 개발용(샌드박스) 진단은 재시작 뒤 이어 볼 필요가 없어 제외."""
        return STATUS_TRAITS[session.status].archived and session.context.run_type is not RunType.TEST
