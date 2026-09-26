"""테스트 공통 설정."""

import pytest

from app import usage


@pytest.fixture(autouse=True)
def _usage_log_to_tmp(tmp_path, monkeypatch):
    """사용량 기록이 실제 ``logs/usage.jsonl``을 건드리지 않게 한다.

    에이전트가 호출 1건마다 ``record()``를 남기므로, 막아두지 않으면 테스트를 돌릴
    때마다 스텁의 가짜 토큰 값이 운영 집계에 섞인다. 실제로 그렇게 섞인 기록이
    56건 있었다(``subject_id``가 ``prod-1`` 같은 테스트 값).
    """
    monkeypatch.setattr(usage, "USAGE_LOG", tmp_path / "usage.jsonl")
