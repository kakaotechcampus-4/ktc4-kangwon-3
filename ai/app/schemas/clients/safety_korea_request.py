"""국가기술표준원 제품안전정보센터 외부 API 요청 파라미터 모델."""

from pydantic import BaseModel


class SafetyKoreaSearchRequest(BaseModel):
    """SafetyKorea 검색 요청 (인증·리콜 공통).

    Args:
        condition_key: 검색 구분.
            KC인증: all, certNum, productName, modelName, certDate, signDate.
            국내리콜: all, barcodeNum, recallProductName, recallBrandName,
                     recallModelName, certNum, publishDate.
            국외리콜: all, recallProductName, recallBrandName,
                     recallModelName, publishDate, fRecallUid.
        condition_value: 검색어.
    """

    condition_key: str
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
