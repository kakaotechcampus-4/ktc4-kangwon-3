"""진단 세션 실행 한도 (#264).

동시 실행·대기 상한·보관 시간은 환경변수(ai/.env)로 덮어쓸 수 있다. 비우면 아래 기본값.
기동할 때 한 번 읽으므로 바꾼 값은 서버를 다시 띄워야 반영된다.
"""

import os
from collections.abc import Mapping

from dotenv import dotenv_values

from .errors import ConfigError
from .settings import ENV_FILE


def env_int(environ: Mapping[str, str | None], name: str, default: int) -> int:
    """1 이상의 정수 환경변수를 읽는다. 비어 있으면 기본값.

    Args:
        environ: 환경변수 표.
        name: 환경변수 이름.
        default: 비어 있을 때 쓸 값.

    Returns:
        int: 읽은 값.

    Raises:
        ConfigError: 정수가 아니거나 1보다 작은 경우.
    """
    raw = (environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name}은 정수여야 합니다: {raw!r}") from None
    if value < 1:
        raise ConfigError(f"{name}은 1 이상이어야 합니다: {value}")
    return value


def check_session_limits(max_running: int, max_inflight: int, max_dev_inflight: int) -> None:
    """세션 상한끼리 맞는지 확인한다.

    Args:
        max_running: 동시 실행 상한.
        max_inflight: 대기 + 실행 중 세션 상한.
        max_dev_inflight: 샌드박스 대기 + 실행 중 상한.

    Raises:
        ConfigError: 동시 실행 상한이나 샌드박스 상한이 대기 + 실행 중 상한보다 큰 경우.
    """
    if max_running > max_inflight:
        raise ConfigError(f"MAX_RUNNING_SESSIONS({max_running})는 MAX_INFLIGHT_SESSIONS({max_inflight}) 이하여야 합니다.")
    if max_dev_inflight > max_inflight:
        raise ConfigError(
            f"MAX_DEV_INFLIGHT_SESSIONS({max_dev_inflight})는 MAX_INFLIGHT_SESSIONS({max_inflight}) 이하여야 합니다.")


# 환경변수가 .env보다 우선 (load_settings와 같음). os.environ에는 넣지 않고 이 파일의 값만 읽음
_ENV = {**dotenv_values(ENV_FILE, encoding="utf-8-sig"), **os.environ}

# 종료된 세션 보관 시간
SESSION_RETENTION_SECONDS = env_int(_ENV, "SESSION_RETENTION_SECONDS", 3600)
# 답변 대기 세션 보관 시간 (질문을 보낸 시각부터). 지나면 지워져 재진단은 404 → BE 실패 처리 (#301)
# 사용자가 답할 시간을 넉넉히 둠. 대기 세션은 원래 입력(이미지 포함)을 들고 있어 메모리와 맞바꿈
AWAITING_INPUT_RETENTION_SECONDS = env_int(_ENV, "AWAITING_INPUT_RETENTION_SECONDS", 24 * 3600)
# 동시 실행 상한. 넘는 세션은 대기
# 추출→선택 10개 동시 실측: 메모리 +58MB, 게이트웨이 거절·지연 없음. 외부 API 제한은 툴·클라이언트에서 따로
MAX_RUNNING_SESSIONS = env_int(_ENV, "MAX_RUNNING_SESSIONS", 10)
# 진단 하나에서 동시에 실행하는 Tool 수. 1이면 순차 실행 (Tool 단계 시간 = 각 Tool 시간의 합)
# 진단 동시 실행과 곱해져 모델 호출이 최대 MAX_RUNNING_SESSIONS × 이 값만큼 동시에 나감. 게이트웨이 거절(429)이 보이면 낮춤
MAX_PARALLEL_TOOLS = env_int(_ENV, "MAX_PARALLEL_TOOLS", 6)
# 대기 + 실행 중 세션 상한. 넘으면 접수 거절 → BE가 대기로 돌렸다가 재요청
# 대기는 실행 자리가 날 때까지 잠깐 쥐는 용도라 실행 상한의 두 배 정도만 둠
# t3.medium, AI 컨테이너 1GB 기준 최악 약 210MB (50개일 때 약 360MB에서 대기 세션당 약 5MB 추정으로 30개분 뺌)
MAX_INFLIGHT_SESSIONS = env_int(_ENV, "MAX_INFLIGHT_SESSIONS", 20)
# 샌드박스 진단 대기 + 실행 중 상한. 운영 진단 실행 자리를 덜 차지하게 따로 둠 (전체 상한에도 같이 셈)
# 실제 파이프라인(모델 호출)이라 3개. 샌드박스 요청 상품 수 상한도 이 값
MAX_DEV_INFLIGHT_SESSIONS = env_int(_ENV, "MAX_DEV_INFLIGHT_SESSIONS", 3)
check_session_limits(MAX_RUNNING_SESSIONS, MAX_INFLIGHT_SESSIONS, MAX_DEV_INFLIGHT_SESSIONS)
# 접수부터 결과까지 최대 시간. 넘으면 시간 초과 실패
SESSION_MAX_DURATION_SECONDS = 600
# 서버 종료 때 실행 중 세션을 기다리는 최대 시간. 진단은 보통 1~2분이라 최대 시간을 넘기면 사실상 멈춘 진단
# 컨테이너 종료 대기 시간(docker-compose stop_grace_period 600초)에서 콜백 마감(15초)과 여유(5초)를 뺌
SESSION_DRAIN_SECONDS = SESSION_MAX_DURATION_SECONDS - 20
# 시간 초과·보관 시간 정리 주기
SESSION_SWEEP_SECONDS = 30
