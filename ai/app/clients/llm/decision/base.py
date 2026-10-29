"""판단 API(/decisions) 클라이언트 공통 베이스.

POST {OPENAI_BASE_URL}/decisions. 요청·응답 형식은 모델 제공사마다 다름 (Jev는 TypeSafe 형식, Luna는 OpenAI 형식).
"""

from abc import ABC, abstractmethod

import httpx

from ....schemas.clients.decision_request import ChoiceQuestion, DecisionRequest, ScoreQuestion
from ....schemas.clients.decision_response import DecisionAnswer, DecisionResponse, DecisionUsage, RefusedAnswer
from ...request import RequestClient
from ..client import TIMEOUT_SECONDS
from .errors import DecisionRequestError, DecisionResponseError

DECISIONS_PATH = "/decisions"
# 맵 대신 배열·null처럼 모양이 다르면 AttributeError·IndexError도 남 (pydantic ValidationError는 ValueError 하위)
_SHAPE_ERRORS = (KeyError, TypeError, ValueError, AttributeError, IndexError)


class DecisionClient(RequestClient[DecisionRequest, DecisionResponse], ABC):
    """판단 API 클라이언트 공통 베이스. 요청 전송·인증·응답 검사만 맡음.

    하위 클라이언트는 `_to_payload`(공통 요청 → 제공사 본문), `_usage_from_payload`(사용량)와
    `_answers_from_payload`(답)만 구현.

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
            DecisionRequestError: 질문 이름·후보 값이 겹쳐 보낼 수 없는 경우. 요청은 보내지 않음.
            httpx.HTTPStatusError: 게이트웨이 응답이 4xx/5xx인 경우.
            httpx.TransportError: 타임아웃·연결 실패로 응답을 받지 못한 경우.
            DecisionResponseError: 응답을 공통 모양으로 바꿀 수 없거나, 질문과 맞지 않는 답(누락·종류 불일치·
                후보에 없는 값·단계 수 불일치)이 있는 경우.
        """
        check_request(request)
        response = self.fetch_parsed(request)
        problems = _answer_problems(request, response)
        if problems:
            raise DecisionResponseError(f"판단 응답이 질문과 맞지 않음: {problems}", usage=response.usage)
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
    def _usage_from_payload(self, body: dict) -> DecisionUsage:
        """제공사 응답 본문에서 모델·토큰 사용량을 읽는다. 필드가 빠졌거나 모양이 다르면 예외를 냄.

        Args:
            body: JSON 응답 본문.

        Returns:
            DecisionUsage: 모델·토큰 사용량.
        """

    @abstractmethod
    def _answers_from_payload(self, body: dict) -> dict[str, DecisionAnswer]:
        """제공사 응답 본문의 답을 질문 이름별 공통 답으로 바꾼다. 필드가 빠졌거나 모양이 다르면 예외를 냄.

        Args:
            body: JSON 응답 본문.

        Returns:
            dict[str, DecisionAnswer]: 질문 이름별 답.
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
        # 답을 못 읽어도 쓴 토큰은 남기도록 사용량을 먼저 따로 읽음
        try:
            usage = self._usage_from_payload(body)
        except _SHAPE_ERRORS as exc:
            raise DecisionResponseError(f"판단 응답 사용량 변환 실패: {type(exc).__name__}: {exc}") from exc
        try:
            return DecisionResponse(answers=self._answers_from_payload(body), usage=usage)
        except _SHAPE_ERRORS as exc:
            raise DecisionResponseError(
                f"판단 응답 답 변환 실패: {type(exc).__name__}: {exc}", usage=usage,
            ) from exc


def check_request(request: DecisionRequest) -> None:
    """제공사 형식으로 보낼 수 있는 요청인지 확인한다.

    Jev는 질문·후보를 이름 키 맵으로 보내 같은 이름이면 앞의 것이 덮이고, 답도 질문 이름으로 찾아 섞임.

    Args:
        request: 판단 요청.

    Raises:
        DecisionRequestError: 질문 이름이나 한 질문 안의 후보·단계 값이 겹치는 경우.
    """
    problems = _duplicates([question.name for question in request.questions], "질문 이름")
    for question in request.questions:
        options = getattr(question, "options", None) or getattr(question, "levels", None) or []
        problems += _duplicates([option.value for option in options], f"{question.name}의 후보·단계 값")
    if problems:
        raise DecisionRequestError(f"보낼 수 없는 판단 요청: {problems}")


def _duplicates(values: list[str], label: str) -> list[str]:
    """겹치는 값이 있으면 문제 설명 하나를 돌려준다."""
    repeated = sorted({value for value in values if values.count(value) > 1})
    return [f"{label} 중복 {repeated}"] if repeated else []


def _answer_problems(request: DecisionRequest, response: DecisionResponse) -> list[str]:
    """질문과 맞지 않는 답을 찾는다. 거부 답은 맞는 것으로 봄.

    Args:
        request: 판단 요청.
        response: 판단 응답.

    Returns:
        list[str]: 문제 설명 (답 누락·종류 불일치·후보에 없는 값·단계 수 불일치). 비면 이상 없음.
    """
    problems = []
    for question in request.questions:
        answer = response.answers.get(question.name)
        if answer is None:
            problems.append(f"{question.name}: 답 없음")
        elif isinstance(answer, RefusedAnswer):
            continue
        elif answer.type != question.type:
            problems.append(f"{question.name}: {question.type} 질문에 {answer.type} 답")
        elif isinstance(question, ChoiceQuestion) and all(answer.choice != option.value for option in question.options):
            problems.append(f"{question.name}: 후보에 없는 답 {answer.choice!r}")
        elif isinstance(question, ScoreQuestion) and len(answer.probabilities) != len(question.levels):
            problems.append(f"{question.name}: 단계 {len(question.levels)}개에 확률 {len(answer.probabilities)}개")
    return problems
