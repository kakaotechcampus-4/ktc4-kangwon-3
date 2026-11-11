import subprocess
import sys
from pathlib import Path

import pytest

from app.config.errors import ConfigError
from app.config.session import check_session_limits, env_int

AI_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("raw", [None, "", "  "])
def test_비어_있으면_기본값을_쓴다(raw):
    assert env_int({"MAX_RUNNING_SESSIONS": raw}, "MAX_RUNNING_SESSIONS", 10) == 10
    assert env_int({}, "MAX_RUNNING_SESSIONS", 10) == 10


def test_값이_있으면_기본값_대신_쓴다():
    assert env_int({"MAX_RUNNING_SESSIONS": " 4 "}, "MAX_RUNNING_SESSIONS", 10) == 4


@pytest.mark.parametrize("raw", ["abc", "2.5", "0", "-1"])
def test_1_이상의_정수가_아니면_거부한다(raw):
    with pytest.raises(ConfigError, match="MAX_RUNNING_SESSIONS"):
        env_int({"MAX_RUNNING_SESSIONS": raw}, "MAX_RUNNING_SESSIONS", 10)


def test_동시_실행이나_샌드박스_상한이_전체_상한보다_크면_거부한다():
    check_session_limits(20, 20, 20)
    with pytest.raises(ConfigError, match="MAX_RUNNING_SESSIONS"):
        check_session_limits(21, 20, 3)
    with pytest.raises(ConfigError, match="MAX_DEV_INFLIGHT_SESSIONS"):
        check_session_limits(10, 20, 21)


def _import_limits(env: dict[str, str]) -> subprocess.CompletedProcess:
    # 기동 때 한 번 읽는 값이라 새 프로세스에서 import
    code = ("from app.config import session as s; "
            "print(s.MAX_RUNNING_SESSIONS, s.MAX_INFLIGHT_SESSIONS, s.MAX_DEV_INFLIGHT_SESSIONS, "
            "s.MAX_PARALLEL_TOOLS, s.SESSION_RETENTION_SECONDS, s.AWAITING_INPUT_RETENTION_SECONDS)")
    return subprocess.run([sys.executable, "-c", code], cwd=AI_ROOT, env={"PATH": "", **env},
                          capture_output=True, text=True, check=False)


def test_환경변수가_있으면_기동할_때_세션_상한과_보관_시간에_반영한다():
    result = _import_limits({
        "MAX_RUNNING_SESSIONS": "3", "MAX_INFLIGHT_SESSIONS": "8", "MAX_DEV_INFLIGHT_SESSIONS": "2",
        "MAX_PARALLEL_TOOLS": "2", "SESSION_RETENTION_SECONDS": "600", "AWAITING_INPUT_RETENTION_SECONDS": "7200",
    })
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["3", "8", "2", "2", "600", "7200"]


def test_상한이_맞지_않으면_기동할_때_실패한다():
    result = _import_limits({"MAX_RUNNING_SESSIONS": "30", "MAX_INFLIGHT_SESSIONS": "20"})
    assert result.returncode != 0
    assert "MAX_RUNNING_SESSIONS(30)는 MAX_INFLIGHT_SESSIONS(20) 이하여야 합니다." in result.stderr
