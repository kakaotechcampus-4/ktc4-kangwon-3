"""세션 실행 자리. 대기 + 실행 중 세션 수를 상한 안에서 셈. 개발용 진단은 따로 정한 상한도 같이 봄."""

from threading import Lock

from ..errors import QueueFullError


class SessionCapacity:
    """대기 + 실행 중 세션 자리를 세고 상한을 넘는 접수를 거절한다."""

    def __init__(self, *, max_inflight: int, max_dev_inflight: int) -> None:
        """자리 계산기를 만든다.

        Args:
            max_inflight: 대기 + 실행 중 세션 상한.
            max_dev_inflight: 개발용 진단의 대기 + 실행 중 상한. 전체 상한에도 같이 셈.
        """
        self._max_inflight = max_inflight
        self._max_dev_inflight = max_dev_inflight
        self._lock = Lock()
        self._inflight = 0
        # 자리를 차지한 개발용 진단의 run_id. 끝나면 개발용 자리도 반납
        self._dev_runs: set[str] = set()

    @property
    def inflight(self) -> int:
        """대기 + 실행 중 세션 수."""
        return self._inflight

    @property
    def dev_inflight(self) -> int:
        """그중 개발용 진단 수."""
        return len(self._dev_runs)

    def check(self, count: int, *, dev: bool = False) -> None:
        """count개를 더 받을 자리가 있는지 확인한다.

        Args:
            count: 새로 받을 세션 수.
            dev: 개발용 진단인지.

        Raises:
            QueueFullError: 개발용 상한 또는 전체 상한을 넘는 경우.
        """
        with self._lock:
            if dev and len(self._dev_runs) + count > self._max_dev_inflight:
                raise QueueFullError(
                    f"개발용 진단 대기열이 가득 찼습니다 ({len(self._dev_runs)}/{self._max_dev_inflight})."
                )
            if self._inflight + count > self._max_inflight:
                raise QueueFullError(f"진단 대기열이 가득 찼습니다 ({self._inflight}/{self._max_inflight}).")

    def take(self, run_ids: list[str], *, dev: bool = False) -> None:
        """실행들의 자리를 차지한다. 상한 확인은 check로 먼저 함.

        Args:
            run_ids: 자리를 차지할 실행 ID.
            dev: 개발용 진단인지.
        """
        with self._lock:
            self._inflight += len(run_ids)
            if dev:
                self._dev_runs.update(run_ids)

    def release(self, run_id: str) -> None:
        """실행 하나의 자리를 반납한다. 완료·실패·답변 대기 모두 실행이 끝나면 반납.

        Args:
            run_id: 끝난 실행 ID.
        """
        with self._lock:
            self._inflight -= 1
            self._dev_runs.discard(run_id)
