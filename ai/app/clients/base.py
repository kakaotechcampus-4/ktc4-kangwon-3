"""외부 통신 클라이언트 공통 베이스."""

import re
import socket
import sys
from functools import lru_cache

import httpx

# data.go.kr serviceKey, 법제처 OC
_SENSITIVE_PARAM_RE = re.compile(r"([?&](?:serviceKey|OC)=)[^&\s'\"]+", re.IGNORECASE)

# 응답 없는 연결을 OS가 끊기까지의 상한(초). langchain-openai 기본값과 같음
DEAD_CONNECTION_SECONDS = 120
# keepalive 탐지: 60초 조용하면 10초 간격으로 3번 확인
_KEEPALIVE_IDLE_SECONDS = 60
_KEEPALIVE_INTERVAL_SECONDS = 10
_KEEPALIVE_COUNT = 3
# transport를 직접 만들면 httpx가 Client의 limits를 무시해 httpx 기본값을 transport에 직접 넣음
_CONNECTION_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)

SocketOption = tuple[int, int, int]


def mask_sensitive_params(text: str) -> str:
    """텍스트 속 URL의 키 쿼리 파라미터 값을 ``***``로 가린다.

    Args:
        text: 가릴 텍스트.

    Returns:
        str: 키 값이 가려진 텍스트.
    """
    return _SENSITIVE_PARAM_RE.sub(r"\1***", text)


@lru_cache
def keepalive_socket_options(dead_connection_seconds: int, platform: str = sys.platform) -> tuple[SocketOption, ...]:
    """죽은 연결을 OS가 감지하도록 거는 TCP 소켓 옵션. 이 OS가 받는 옵션만 남긴다.

    - Linux: keepalive 간격 + TCP_USER_TIMEOUT(dead_connection_seconds)
    - macOS: keepalive 간격
    - Windows: keepalive 켜기만 (간격 조정은 setsockopt로 안 됨)

    Args:
        dead_connection_seconds: 응답 없는 연결을 끊기까지의 상한(초). Linux에서만 그대로 쓰임.
        platform: 대상 OS (sys.platform 형식).

    Returns:
        tuple[SocketOption, ...]: (level, option, value) 목록.
    """
    tcp = socket.IPPROTO_TCP
    candidates: list[tuple[int, str, int]] = [(socket.SOL_SOCKET, "SO_KEEPALIVE", 1)]
    if platform in ("linux", "darwin"):
        candidates += [
            # macOS는 유휴 시간 옵션 이름이 TCP_KEEPALIVE
            (tcp, "TCP_KEEPIDLE" if platform == "linux" else "TCP_KEEPALIVE", _KEEPALIVE_IDLE_SECONDS),
            (tcp, "TCP_KEEPINTVL", _KEEPALIVE_INTERVAL_SECONDS),
            (tcp, "TCP_KEEPCNT", _KEEPALIVE_COUNT),
        ]
    if platform == "linux":
        candidates.append((tcp, "TCP_USER_TIMEOUT", dead_connection_seconds * 1000))
    return _supported([(level, getattr(socket, name), value) for level, name, value in candidates
                       if hasattr(socket, name)])


def _supported(options: list[SocketOption]) -> tuple[SocketOption, ...]:
    # 실제 소켓에 걸어 보고 OS가 거부한 옵션은 뺌 (연결할 때 실패하지 않게)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        accepted = []
        for option in options:
            try:
                probe.setsockopt(*option)
            except OSError:
                continue
            accepted.append(option)
        return tuple(accepted)
    finally:
        probe.close()


class BaseClient:
    """외부 통신 클라이언트 공통 베이스. HTTP 연결을 갖고 닫는 일만 맡는다.

    Args:
        base_url: API 도메인 주소. 서브클래스에서 지정한다.
        timeout: 요청 제한 시간(초). 기본 10초.
        headers: 모든 요청에 포함할 공통 헤더.
        transport: httpx 전송 계층. 테스트에서 가짜 응답을 붙일 때 주입. 주면 dead_connection_seconds는 안 씀.
        dead_connection_seconds: 응답 없는 연결을 OS가 끊기까지의 상한(초). None이면 keepalive 없이 httpx 기본.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
        dead_connection_seconds: int | None = DEAD_CONNECTION_SECONDS,
    ):
        if transport is None and dead_connection_seconds is not None:
            transport = httpx.HTTPTransport(
                socket_options=keepalive_socket_options(dead_connection_seconds), limits=_CONNECTION_LIMITS,
            )
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=headers or {},
            transport=transport,
        )

    # -- 정리 --

    def close(self) -> None:
        """HTTP 클라이언트 연결을 정리한다."""
        self._client.close()
