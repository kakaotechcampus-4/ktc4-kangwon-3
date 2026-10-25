"""외부 통신 클라이언트 공통 베이스."""

import re

import httpx

# data.go.kr serviceKey, 법제처 OC
_SENSITIVE_PARAM_RE = re.compile(r"([?&](?:serviceKey|OC)=)[^&\s'\"]+", re.IGNORECASE)


def mask_sensitive_params(text: str) -> str:
    """텍스트 속 URL의 키 쿼리 파라미터 값을 ``***``로 가린다.

    Args:
        text: 가릴 텍스트.

    Returns:
        str: 키 값이 가려진 텍스트.
    """
    return _SENSITIVE_PARAM_RE.sub(r"\1***", text)


class BaseClient:
    """외부 통신 클라이언트 공통 베이스. HTTP 연결을 갖고 닫는 일만 맡는다.

    Args:
        base_url: API 도메인 주소. 서브클래스에서 지정한다.
        timeout: 요청 제한 시간(초). 기본 10초.
        headers: 모든 요청에 포함할 공통 헤더.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=headers or {},
        )

    # -- 정리 --

    def close(self) -> None:
        """HTTP 클라이언트 연결을 정리한다."""
        self._client.close()
