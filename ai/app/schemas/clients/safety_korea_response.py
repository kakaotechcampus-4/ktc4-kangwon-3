"""국가기술표준원 제품안전정보센터 외부 API 응답 모델."""

from __future__ import annotations

from pydantic import BaseModel


# -- KC인증정보 --

class CertFactory(BaseModel):
    """KC인증 공장 정보."""

    makerName: str | None = None
    makerCntryName: str | None = None


class CertItem(BaseModel):
    """KC인증정보 단건."""

    certUid: int | None = None
    certOrganName: str | None = None
    certNum: str | None = None
    certState: str | None = None
    certDiv: str | None = None
    certDate: str | None = None
    certChgDate: str | None = None
    certChgReason: str | None = None
    firstCertNum: str | None = None
    productName: str | None = None
    brandName: str | None = None
    modelName: str | None = None
    categoryName: str | None = None
    importDiv: str | None = None
    makerName: str | None = None
    makerCntryName: str | None = None
    importerName: str | None = None
    remark: str | None = None
    signDate: str | None = None
    derivationModels: list[str] | None = None
    certificationImageUrls: list[str] | None = None
    factories: list[CertFactory] | None = None
    similarCertifications: list[CertItem] | None = None


class CertSearchResponse(BaseModel):
    """KC인증정보 조회 응답.

    Attributes:
        items: 인증정보 목록.
    """

    items: list[CertItem]


# -- 국내리콜 --

class RecallFile(BaseModel):
    """국내리콜 첨부파일."""

    fileDiv: str | None = None
    imageUrl: str | None = None


class RecallItem(BaseModel):
    """국내리콜정보 단건."""

    recallUid: str | None = None
    recallProductName: str | None = None
    recallBrandName: str | None = None
    recallModelName: str | None = None
    recallModelCnt: int | None = None
    recallTypeName: str | None = None
    recallMeans: str | None = None
    barcodeNum: str | None = None
    categoryName: str | None = None
    certNum: str | None = None
    productItemName: str | None = None
    recallCmpnyDivName: str | None = None
    recallInqryTel: str | None = None
    recallCmpnyName: str | None = None
    recallCmpnySsn: str | None = None
    recallFrgnCmpnyName: str | None = None
    makerCntryName: str | None = None
    makerName: str | None = None
    makingCntryName: str | None = None
    publishDate: str | None = None
    publishRecallVol: str | None = None
    recallActionAmt: str | None = None
    recallStaDate: str | None = None
    recallEndDate: str | None = None
    harmDscr: str | None = None
    accidentCaseDscr: str | None = None
    publishActionDscr: str | None = None
    recallFiles: list[RecallFile] | None = None


class RecallSearchResponse(BaseModel):
    """국내리콜정보 조회 응답.

    Attributes:
        items: 리콜정보 목록.
    """

    items: list[RecallItem]


# -- 국외리콜 --

class ForeignRecallItem(BaseModel):
    """국외리콜정보 단건."""

    fRecallUid: str | None = None
    recallModelName: str | None = None
    recallModelCnt: str | None = None
    recallProductName: str | None = None
    recallBrandName: str | None = None
    makerName: str | None = None
    makingCntryName: str | None = None
    recallTypeName: str | None = None
    recallPblshCntryName: str | None = None
    recallPblshOrgnName: str | None = None
    recallMeans: str | None = None
    violateDscr: str | None = None
    accidentCaseDscr: str | None = None
    publishActionDscr: str | None = None
    recallProductDscr: str | None = None
    recallUrl: str | None = None
    publishDate: str | None = None
    signDttm: str | None = None
    imageUrl: str | None = None


class ForeignRecallSearchResponse(BaseModel):
    """국외리콜정보 조회 응답.

    Attributes:
        items: 국외리콜 목록.
    """

    items: list[ForeignRecallItem]
