"""요청 하나를 보내고 응답 스키마로 바꾸는 클라이언트 베이스."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from xml.etree.ElementTree import Element, fromstring

import httpx

from .base import BaseClient, mask_sensitive_params

RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class RequestClient(BaseClient, ABC, Generic[RequestT, ResponseT]):
    """요청 하나를 보내고 원문 응답을 응답 스키마로 바꾸는 클라이언트 베이스.

    하위 클라이언트는 `_send`(요청 방법)와 `_parse`(원문 → 응답 스키마 변환 방법)를 구현한다.
    호출하는 쪽은 원문이 필요하면 `fetch_raw`, 스키마가 필요하면 `fetch_parsed`를 쓴다.
    """

    # -- 조회 --

    def fetch_raw(self, request: RequestT) -> httpx.Response:
        """요청을 보내고 파싱 전 원문 응답을 반환한다.

        Args:
            request: 조회 요청 파라미터.

        Returns:
            httpx.Response: 파싱 전 원문 응답.
        """
        return self._send(request)

    def fetch_parsed(self, request: RequestT) -> ResponseT:
        """요청을 보내고 응답 스키마로 변환해 반환한다.

        Args:
            request: 조회 요청 파라미터.

        Returns:
            ResponseT: 응답 스키마.
        """
        return self._parse(self._send(request))

    # -- 인터페이스 (하위 클라이언트 구현) --

    @abstractmethod
    def _send(self, request: RequestT) -> httpx.Response:
        """이 API에 요청을 보내고 원문 응답을 반환한다.

        Args:
            request: 조회 요청 파라미터.

        Returns:
            httpx.Response: 원문 응답.
        """

    @abstractmethod
    def _parse(self, raw: httpx.Response) -> ResponseT:
        """이 API의 원문 응답을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 원문 응답.

        Returns:
            ResponseT: 응답 스키마.
        """

    # -- 요청 --

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        """GET 요청을 보내고 응답을 반환한다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            params: 쿼리 파라미터.

        Returns:
            httpx.Response: HTTP 응답 객체.

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 응답 시.
        """
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response

    def _post(self, path: str, json: dict | None = None, data: dict | None = None) -> httpx.Response:
        """POST 요청을 보내고 응답을 반환한다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            json: JSON 요청 본문.
            data: form 요청 본문 (application/x-www-form-urlencoded).

        Returns:
            httpx.Response: HTTP 응답 객체.

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 응답 시.
        """
        response = self._client.post(path, json=json, data=data)
        response.raise_for_status()
        return response

    @staticmethod
    def _mask_url(error: httpx.HTTPStatusError) -> httpx.HTTPStatusError:
        """HTTPStatusError 메시지에서 민감한 쿼리 파라미터를 마스킹한다.

        Args:
            error: 원본 예외.

        Returns:
            httpx.HTTPStatusError: URL이 마스킹된 새 예외.
        """
        masked_msg = mask_sensitive_params(str(error))
        return httpx.HTTPStatusError(
            message=masked_msg,
            request=error.request,
            response=error.response,
        )

    # -- 응답 파싱 --

    def _parse_json(self, response: httpx.Response) -> dict:
        """응답 본문을 JSON으로 파싱한다.

        Args:
            response: HTTP 응답 객체.

        Returns:
            dict: 파싱된 JSON 데이터.
        """
        return response.json()

    def _parse_xml(self, response: httpx.Response) -> Element:
        """응답 본문을 XML Element로 파싱한다.

        Args:
            response: HTTP 응답 객체.

        Returns:
            Element: 파싱된 XML 루트 엘리먼트.
        """
        return fromstring(response.text)
