"""실제 외부 API 테스트 공통 설정.

키는 ai/.env 또는 환경변수에서 읽는다. 키가 없으면 실패가 아니라 건너뛴다 (CI에는 .env가 없음).
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name}이 없어 실제 API 테스트를 건너뜀")
    return value


@pytest.fixture
def law_oc() -> str:
    """법제처 OC."""
    return _require_env("LAW_GO_KR_OC")
