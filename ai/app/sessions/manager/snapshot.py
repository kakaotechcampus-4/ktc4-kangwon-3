"""세션 관리자 현황. 지표 수집처럼 바깥에서 한 번에 읽어 가는 값 묶음."""

from dataclasses import dataclass
from typing import Literal

from ...domain.context import RunType
from ...schemas.session import SessionStatus

# 접수 거절 사유. 대기열 가득(429) / 실행 중 상품 섞임(409)
RejectReason = Literal["queue_full", "conflict"]


@dataclass(frozen=True)
class SessionSnapshot:
    """읽은 순간의 세션 관리자 현황. 누적 값은 서버 시작부터 셈.

    Attributes:
        status_counts: 상태별 보관 중인 세션 수. 모든 상태를 0 포함해 담음.
        inflight: 대기 + 실행 중 자리 수. 개발용 포함.
        dev_inflight: 그중 개발용 진단 수.
        max_running: 동시 실행 상한.
        max_inflight: 대기 + 실행 중 상한.
        max_dev_inflight: 개발용 대기 + 실행 중 상한.
        accepted: 실행 종류별 누적 접수 세션 수.
        rejected: 거절 사유별 누적 거절 요청 수. 요청 하나에 상품이 여럿이어도 1.
        awaiting_replaced: 새 접수로 버린 답변 대기 세션 누적 수 (#451).
    """

    status_counts: dict[SessionStatus, int]
    inflight: int
    dev_inflight: int
    max_running: int
    max_inflight: int
    max_dev_inflight: int
    accepted: dict[RunType, int]
    rejected: dict[RejectReason, int]
    awaiting_replaced: int
