"""국가기술표준원 제품안전정보센터 외부 API 요청 파라미터 모델."""

from typing import Literal

from pydantic import BaseModel

# 정의되지 않은 검색 구분을 넣으면 API가 에러 대신 필터 없는 전체 목록(KC인증 약 105만 건, 748MB)을 돌려준다.
# 허용값이 API마다 달라 요청 모델을 나누고, 요청을 보내기 전에 막는다 (#185).


class CertSearchRequest(BaseModel):
    """KC인증정보 검색 요청.

    Args:
        condition_key: 검색 구분. all, certNum, productName, modelName, certDate, signDate.
        condition_value: 검색어.
    """

    condition_key: Literal["all", "certNum", "productName", "modelName", "certDate", "signDate"]
    condition_value: str


class RecallSearchRequest(BaseModel):
    """국내리콜정보 검색 요청.

    Args:
        condition_key: 검색 구분. all, barcodeNum, recallProductName, recallBrandName,
            recallModelName, certNum, publishDate.
        condition_value: 검색어.
    """

    condition_key: Literal[
        "all", "barcodeNum", "recallProductName", "recallBrandName",
        "recallModelName", "certNum", "publishDate",
    ]
    condition_value: str


class ForeignRecallSearchRequest(BaseModel):
    """국외리콜정보 검색 요청.

    Args:
        condition_key: 검색 구분. all, recallProductName, recallBrandName,
            recallModelName, publishDate, fRecallUid.
        condition_value: 검색어.
    """

    condition_key: Literal[
        "all", "recallProductName", "recallBrandName",
        "recallModelName", "publishDate", "fRecallUid",
    ]
    condition_value: str


class CertDetailRequest(BaseModel):
    """KC인증정보 상세 조회 요청.

    Args:
        cert_num: KC 인증번호.
    """

    cert_num: str


class RecallDetailRequest(BaseModel):
    """국내리콜 상세 조회 요청.

    Args:
        recall_uid: 리콜 아이디.
    """

    recall_uid: str
