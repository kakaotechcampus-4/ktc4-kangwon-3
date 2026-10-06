"""국가기술표준원 제품안전정보센터 외부 API 응답 모델."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# -- KC인증정보 --

class CertFactory(BaseModel):
    """KC인증 공장 정보."""

    model_config = ConfigDict(populate_by_name=True)

    maker_name: str | None = Field(None, alias="makerName")
    maker_cntry_name: str | None = Field(None, alias="makerCntryName")


class CertItem(BaseModel):
    """KC인증정보 단건."""

    model_config = ConfigDict(populate_by_name=True)

    cert_uid: int | None = Field(None, alias="certUid")
    cert_organ_name: str | None = Field(None, alias="certOrganName")
    cert_num: str | None = Field(None, alias="certNum")
    cert_state: str | None = Field(None, alias="certState")
    cert_div: str | None = Field(None, alias="certDiv")
    cert_date: str | None = Field(None, alias="certDate")
    cert_chg_date: str | None = Field(None, alias="certChgDate")
    cert_chg_reason: str | None = Field(None, alias="certChgReason")
    first_cert_num: str | None = Field(None, alias="firstCertNum")
    product_name: str | None = Field(None, alias="productName")
    brand_name: str | None = Field(None, alias="brandName")
    model_name: str | None = Field(None, alias="modelName")
    category_name: str | None = Field(None, alias="categoryName")
    import_div: str | None = Field(None, alias="importDiv")
    maker_name: str | None = Field(None, alias="makerName")
    maker_cntry_name: str | None = Field(None, alias="makerCntryName")
    importer_name: str | None = Field(None, alias="importerName")
    remark: str | None = None
    sign_date: str | None = Field(None, alias="signDate")
    derivation_models: list[str] | None = Field(None, alias="derivationModels")
    certification_image_urls: list[str] | None = Field(None, alias="certificationImageUrls")
    factories: list[CertFactory] | None = None
    similar_certifications: list[CertItem] | None = Field(None, alias="similarCertifications")


class CertSearchResponse(BaseModel):
    """KC인증정보 조회 응답.

    Attributes:
        items: 인증정보 목록.
    """

    items: list[CertItem]


# -- 국내리콜 --

class RecallFile(BaseModel):
    """국내리콜 첨부파일."""

    model_config = ConfigDict(populate_by_name=True)

    file_div: str | None = Field(None, alias="fileDiv")
    image_url: str | None = Field(None, alias="imageUrl")


class RecallItem(BaseModel):
    """국내리콜정보 단건."""

    model_config = ConfigDict(populate_by_name=True)

    recall_uid: str | None = Field(None, alias="recallUid")
    recall_product_name: str | None = Field(None, alias="recallProductName")
    recall_brand_name: str | None = Field(None, alias="recallBrandName")
    recall_model_name: str | None = Field(None, alias="recallModelName")
    recall_model_cnt: int | None = Field(None, alias="recallModelCnt")
    recall_type_name: str | None = Field(None, alias="recallTypeName")
    recall_means: str | None = Field(None, alias="recallMeans")
    barcode_num: str | None = Field(None, alias="barcodeNum")
    category_name: str | None = Field(None, alias="categoryName")
    cert_num: str | None = Field(None, alias="certNum")
    product_item_name: str | None = Field(None, alias="productItemName")
    recall_cmpny_div_name: str | None = Field(None, alias="recallCmpnyDivName")
    recall_inqry_tel: str | None = Field(None, alias="recallInqryTel")
    recall_cmpny_name: str | None = Field(None, alias="recallCmpnyName")
    recall_cmpny_ssn: str | None = Field(None, alias="recallCmpnySsn")
    recall_frgn_cmpny_name: str | None = Field(None, alias="recallFrgnCmpnyName")
    maker_cntry_name: str | None = Field(None, alias="makerCntryName")
    maker_name: str | None = Field(None, alias="makerName")
    making_cntry_name: str | None = Field(None, alias="makingCntryName")
    publish_date: str | None = Field(None, alias="publishDate")
    publish_recall_vol: str | None = Field(None, alias="publishRecallVol")
    recall_action_amt: str | None = Field(None, alias="recallActionAmt")
    recall_sta_date: str | None = Field(None, alias="recallStaDate")
    recall_end_date: str | None = Field(None, alias="recallEndDate")
    harm_dscr: str | None = Field(None, alias="harmDscr")
    accident_case_dscr: str | None = Field(None, alias="accidentCaseDscr")
    publish_action_dscr: str | None = Field(None, alias="publishActionDscr")
    recall_files: list[RecallFile] | None = Field(None, alias="recallFiles")


class RecallSearchResponse(BaseModel):
    """국내리콜정보 조회 응답.

    Attributes:
        items: 리콜정보 목록.
    """

    items: list[RecallItem]


# -- 국외리콜 --

class ForeignRecallItem(BaseModel):
    """국외리콜정보 단건."""

    model_config = ConfigDict(populate_by_name=True)

    f_recall_uid: str | None = Field(None, alias="fRecallUid")
    recall_model_name: str | None = Field(None, alias="recallModelName")
    recall_model_cnt: str | None = Field(None, alias="recallModelCnt")
    recall_product_name: str | None = Field(None, alias="recallProductName")
    recall_brand_name: str | None = Field(None, alias="recallBrandName")
    maker_name: str | None = Field(None, alias="makerName")
    making_cntry_name: str | None = Field(None, alias="makingCntryName")
    recall_type_name: str | None = Field(None, alias="recallTypeName")
    recall_pblsh_cntry_name: str | None = Field(None, alias="recallPblshCntryName")
    recall_pblsh_orgn_name: str | None = Field(None, alias="recallPblshOrgnName")
    recall_means: str | None = Field(None, alias="recallMeans")
    violate_dscr: str | None = Field(None, alias="violateDscr")
    accident_case_dscr: str | None = Field(None, alias="accidentCaseDscr")
    publish_action_dscr: str | None = Field(None, alias="publishActionDscr")
    recall_product_dscr: str | None = Field(None, alias="recallProductDscr")
    recall_url: str | None = Field(None, alias="recallUrl")
    publish_date: str | None = Field(None, alias="publishDate")
    sign_dttm: str | None = Field(None, alias="signDttm")
    image_url: str | None = Field(None, alias="imageUrl")


class ForeignRecallSearchResponse(BaseModel):
    """국외리콜정보 조회 응답.

    Attributes:
        items: 국외리콜 목록.
    """

    items: list[ForeignRecallItem]
