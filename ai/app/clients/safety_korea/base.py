"""국가기술표준원 제품안전정보센터 클라이언트 공통 베이스."""

from typing import Any

import httpx

from ..request import RequestClient, RequestT, ResponseT
from ...utils.date_range import is_date_prefix_within_years

# 리콜은 공표일 기준 최근 5년만 수집
RECALL_COLLECTION_YEARS = 5

# 정상 결과코드: 2000 성공, 2004 데이터 없음
_OK_RESULT_CODES = ("2000", "2004")


class SafetyKoreaBaseClient(RequestClient[RequestT, ResponseT]):
    """국가기술표준원 제품안전정보센터(SafetyKorea) 클라이언트 공통 베이스.

    방식 : GET/JSON
    인증 : AuthKey 헤더 (safetykorea.kr 자체 발급).
    비고
        KC인증정보 조회/상세, 국내리콜 조회/상세, 국외리콜 조회 5개가 같은 인증·응답 형식을 씀.
        응답은 {resultCode, resultMsg, resultData}로 감싸져 옴.
        하위 클라이언트는 `_get_with_auth`로 요청하고 `_send`·`_parse`를 구현.
    """

    API = "safety_korea"

    def __init__(self, auth_key: str):
        super().__init__(
            base_url="https://www.safetykorea.kr",
            timeout=30.0,
            headers={"AuthKey": auth_key},
        )

    def _get_with_auth(self, path: str, params: dict) -> httpx.Response:
        """AuthKey 헤더를 붙인 GET 요청을 보낸다.

        Args:
            path: base_url 뒤에 붙는 요청 경로.
            params: 쿼리 파라미터.

        Returns:
            httpx.Response: JSON 원문 응답.

        Raises:
            RuntimeError: 인증 실패(302 Redirect) 시.
            httpx.HTTPStatusError: 그 밖의 3xx/4xx/5xx 응답 시.
        """
        try:
            return self._get(path, params=params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 302:
                raise RuntimeError(
                    "SafetyKorea 인증 실패: AuthKey가 유효하지 않습니다 (302 Redirect)"
                ) from None
            raise

    @staticmethod
    def _check_recall_publish_date(condition_key: str, condition_value: str) -> None:
        """공표일 검색이면 검색값이 수집 기간(최근 5년) 안인지 요청 전에 확인한다.

        API는 공표일을 앞부분 일치(YYYY·YYYYMM·YYYYMMDD)로만 검색하고 기간 검색은 지원하지 않음.
        형식이 틀리면 오류 없이 0건이 오므로 형식도 함께 확인. 공표일 외 검색은 확인하지 않음.

        Args:
            condition_key: 검색 구분.
            condition_value: 검색어.

        Raises:
            ValueError: 공표일 검색값의 형식이 틀렸거나 수집 기간보다 오래된 경우.
        """
        if condition_key != "publishDate":
            return
        if not is_date_prefix_within_years(condition_value, RECALL_COLLECTION_YEARS):
            raise ValueError(
                f"리콜은 최근 {RECALL_COLLECTION_YEARS}년만 수집함: 공표일 검색값 {condition_value!r}이 기간 밖"
            )

    def _parse_result_data(self, raw: httpx.Response) -> Any:
        """원문 응답의 결과코드를 확인하고 resultData를 꺼낸다.

        명세상 Invalid IP(4001)·Invalid Parameter(4005)·서버 오류(5000)도 HTTP 200 본문으로 올 수 있음.
        그대로 넘기면 "0건"과 구분할 수 없으므로 성공(2000)·데이터 없음(2004) 외에는 수신 실패로 올림.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            Any: resultData 값. 목록 조회는 list, 상세 조회는 dict. 없으면 None.

        Raises:
            RuntimeError: resultCode가 2000·2004가 아니거나 없는 경우.
        """
        data = self._parse_json(raw)
        # 명세 예시에 문자열·숫자가 섞여 있어 문자열로 맞춰 비교
        result_code = str(data.get("resultCode"))
        if result_code not in _OK_RESULT_CODES:
            raise RuntimeError(f"SafetyKorea API 오류: resultCode={result_code} — {data.get('resultMsg')}")
        return data.get("resultData")

    @classmethod
    def _clean_values(cls, value: Any) -> Any:
        """원문 값의 앞뒤 공백을 지우고 정보 없음 표시("-", 빈 문자열)를 None으로 바꾼다.

        국외리콜은 값 끝에 줄바꿈·특수 공백(\\xa0)이 붙고, 값이 없으면 "-"로 옴. 중첩된 dict·list도 처리.

        Args:
            value: resultData 항목 또는 그 안의 값.

        Returns:
            Any: 정리된 값. 구조(dict·list)는 그대로 유지.
        """
        if isinstance(value, dict):
            return {key: cls._clean_values(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._clean_values(item) for item in value]
        if isinstance(value, str):
            text = value.strip()
            return None if text in ("", "-") else text
        return value
