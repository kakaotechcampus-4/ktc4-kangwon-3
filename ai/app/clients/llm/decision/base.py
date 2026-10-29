"""판단 API(/decisions) 클라이언트 공통 베이스.

POST {OPENAI_BASE_URL}/decisions. 요청·응답 형식은 모델 제공사마다 다름 (Jev는 TypeSafe 형식, Luna는 OpenAI 형식).
"""

from abc import ABC, abstractmethod

import httpx

from ....schemas.clients.decision_request import DecisionRequest
from ....schemas.clients.decision_response import DecisionResponse
from ...request import RequestClient
from ..client import TIMEOUT_SECONDS
from .errors import DecisionResponseError

DECISIONS_PATH = "/decisions"


class DecisionClient(RequestClient[DecisionRequest, DecisionResponse], ABC):
    """판단 API 클라이언트 공통 베이스. 요청 전송·인증·응답 검사만 맡음.

    하위 클라이언트는 `_to_payload`(공통 요청 → 제공사 본문)와 `_from_payload`(제공사 본문 → 공통 응답)만 구현.

    Args:
        base_url: 게이트웨이 주소 (OPENAI_BASE_URL).
        api_key: ML API 키 (OPENAI_API_KEY).
        timeout: 요청 하나의 대기 상한(초).
        transport: httpx 전송 계층. 테스트에서 가짜 응답을 붙일 때 주입.
    """

    def __init__(
        self, base_url: str, api_key: str, *, timeout: float = TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url.rstrip("/"), timeout=timeout, headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        """질문을 보내고 질문마다 답을 받는다. 에이전트가 부르는 입구.

        Args:
            request: 판단 요청.

        Returns:
            DecisionResponse: 질문 이름별 답과 토큰 사용량.

        Raises:
            httpx.HTTPStatusError: 게이트웨이 응답이 4xx/5xx인 경우.
            httpx.TransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
            DecisionResponseError: 응답을 공통 모양으로 바꿀 수 없거나 답이 빠진 질문이 있는 경우.
        """
        response = self.fetch_parsed(request)
        missing = [question.name for question in request.questions if question.name not in response.answers]
        if missing:
            raise DecisionResponseError(f"판단 응답에 답이 없는 질문: {missing}")
        return response

    # -- 인터페이스 (하위 클라이언트 구현) --

    @abstractmethod
    def _to_payload(self, request: DecisionRequest) -> dict:
        """공통 요청을 제공사 요청 본문으로 바꾼다.

        Args:
            request: 판단 요청.

        Returns:
            dict: JSON 요청 본문.
        """

    @abstractmethod
    def _from_payload(self, body: dict) -> DecisionResponse:
        """제공사 응답 본문을 공통 응답으로 바꾼다. 필드가 빠졌거나 모양이 다르면 예외를 냄.

        Args:
            body: JSON 응답 본문.

        Returns:
            DecisionResponse: 질문 이름별 답과 토큰 사용량.
        """

    # -- RequestClient 구현 --

    def _send(self, request: DecisionRequest) -> httpx.Response:
        """판단 요청을 POST로 보낸다.

        Args:
            request: 판단 요청.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            httpx.HTTPStatusError: 게이트웨이 응답이 4xx/5xx인 경우.
        """
        return self._post(DECISIONS_PATH, json=self._to_payload(request))

    def _parse(self, raw: httpx.Response) -> DecisionResponse:
        """JSON 원문을 공통 응답으로 바꾼다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            DecisionResponse: 질문 이름별 답과 토큰 사용량.

        Raises:
            DecisionResponseError: JSON이 아니거나, 하위 클라이언트가 변환하지 못한 경우.
        """
        try:
            body = self._parse_json(raw)
        except ValueError as exc:
            raise DecisionResponseError(f"판단 응답이 JSON이 아님: {raw.text[:200]!r}") from exc
        if not isinstance(body, dict):
            raise DecisionResponseError(f"판단 응답 본문이 객체가 아님: {type(body).__name__}")
        try:
            return self._from_payload(body)
        # pydantic ValidationError는 ValueError 하위
        except (KeyError, TypeError, ValueError) as exc:
            raise DecisionResponseError(f"판단 응답 변환 실패: {type(exc).__name__}: {exc}") from exc
