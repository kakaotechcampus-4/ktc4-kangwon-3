"""세션 자리 계산: 전체·개발용 상한 확인과 자리 차지·반납을 확인한다."""

import pytest

from app.sessions.errors import QueueFullError
from app.sessions.manager.capacity import SessionCapacity


def test_상한까지는_받고_넘으면_거절한다():
    capacity = SessionCapacity(max_inflight=2, max_dev_inflight=1)
    capacity.check(2)
    capacity.take(["r-1", "r-2"])

    with pytest.raises(QueueFullError, match=r"\(2/2\)"):
        capacity.check(1)


def test_개발용은_따로_정한_상한도_넘으면_거절한다():
    capacity = SessionCapacity(max_inflight=5, max_dev_inflight=1)
    capacity.take(["dev-1"], dev=True)

    with pytest.raises(QueueFullError, match="개발용"):
        capacity.check(1, dev=True)
    # 운영 접수는 막지 않음
    capacity.check(1)


def test_개발용도_전체_상한에_같이_센다():
    capacity = SessionCapacity(max_inflight=1, max_dev_inflight=3)
    capacity.take(["dev-1"], dev=True)

    assert (capacity.inflight, capacity.dev_inflight) == (1, 1)
    with pytest.raises(QueueFullError):
        capacity.check(1)


def test_반납하면_자리와_개발용_자리가_돌아온다():
    capacity = SessionCapacity(max_inflight=2, max_dev_inflight=1)
    capacity.take(["r-1"])
    capacity.take(["dev-1"], dev=True)

    capacity.release("dev-1")
    capacity.release("r-1")

    assert (capacity.inflight, capacity.dev_inflight) == (0, 0)
    capacity.check(2)
    capacity.check(1, dev=True)
