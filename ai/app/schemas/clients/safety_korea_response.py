"""국가기술표준원 제품안전정보센터 외부 API 응답 모델."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# -- KC인증정보 --

class CertFactory(BaseModel):
    """KC인증 공장 정보.

    Attributes:
        manufacturer_name: 제조사명.
        manufacture_country: 제조국명.
    """

    model_config = ConfigDict(populate_by_name=True)

    manufacturer_name: str | None = Field(None, alias="makerName")
    manufacture_country: str | None = Field(None, alias="makerCntryName")


class CertItem(BaseModel):
    """KC인증정보 단건.

    Attributes:
        certification_id: 인증정보 아이디.
        certification_body_name: 인증기관명 (예: 한국산업기술시험원(KTL)).
        certification_number: 인증번호(필증번호).
        certification_status: 인증상태 (적합, 반납, 기간만료, 안전인증취소, 개선명령 등).
        certification_type: 인증구분 (전안법·어린이법의 안전인증·안전확인 대상).
        certified_date: 인증일자.
        status_changed_date: 인증상태 변경일자.
        status_change_reason: 인증상태 변경사유 (예: 자진반납).
        original_certification_number: 최초인증번호.
        product_name: 제품명.
        brand_name: 브랜드명.
        model_name: 모델명(로트번호).
        category_name: 법정 제품분류명.
        import_type: 수입/제조 구분.
        manufacturer_name: 제조사명.
        manufacture_country: 제조국명.
        importer_name: 수입사명.
        remarks: 상세내용.
        registered_date: 등록일 (인증정보가 제품안전정보센터에 등록된 날).
        derived_models: 파생모델 목록.
        certification_image_urls: 인증서 이미지 URL 목록.
        factories: 공장 목록.
        similar_certifications: 같은 최초인증번호를 쓰는 다른 인증 목록.
    """

    model_config = ConfigDict(populate_by_name=True)

    certification_id: int | None = Field(None, alias="certUid")
    certification_body_name: str | None = Field(None, alias="certOrganName")
    certification_number: str | None = Field(None, alias="certNum")
    certification_status: str | None = Field(None, alias="certState")
    certification_type: str | None = Field(None, alias="certDiv")
    certified_date: str | None = Field(None, alias="certDate")
    status_changed_date: str | None = Field(None, alias="certChgDate")
    status_change_reason: str | None = Field(None, alias="certChgReason")
    original_certification_number: str | None = Field(None, alias="firstCertNum")
    product_name: str | None = Field(None, alias="productName")
    brand_name: str | None = Field(None, alias="brandName")
    model_name: str | None = Field(None, alias="modelName")
    category_name: str | None = Field(None, alias="categoryName")
    import_type: str | None = Field(None, alias="importDiv")
    manufacturer_name: str | None = Field(None, alias="makerName")
    manufacture_country: str | None = Field(None, alias="makerCntryName")
    importer_name: str | None = Field(None, alias="importerName")
    remarks: str | None = Field(None, alias="remark")
    registered_date: str | None = Field(None, alias="signDate")
    derived_models: list[str] | None = Field(None, alias="derivationModels")
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
    """국내리콜 사진.

    Attributes:
        file_type: 사진 구분 (예: 부분사진).
        image_url: 사진 URL.
    """

    model_config = ConfigDict(populate_by_name=True)

    file_type: str | None = Field(None, alias="fileDiv")
    image_url: str | None = Field(None, alias="imageUrl")


class RecallItem(BaseModel):
    """국내리콜정보 단건.

    Attributes:
        recall_id: 리콜 아이디.
        recall_product_name: 제품명.
        recall_brand_name: 브랜드명.
        recall_model_name: 리콜 모델 목록 (쉼표 구분 문자열).
        recall_model_count: 리콜 모델 개수.
        recall_type: 리콜종류 (자발적리콜, 권고에따른리콜, 명령에따른리콜).
        recall_method: 리콜방법 (예: 환불, 수거).
        barcode_number: 바코드.
        category_name: 제품분류명.
        certification_number: 인증번호 목록 (쉼표 구분 문자열).
        product_group_name: 제품 품목명 (예: 전기용품>가전제품).
        recall_company_type: 리콜 사업자 구분 (수입, 제조, 판매, 리콜대행).
        recall_contact_phone: 리콜 문의전화.
        recall_company_name: 리콜 사업자명.
        recall_company_business_number: 리콜 사업자번호.
        foreign_company_name: 해외사업자명 (리콜대행인 경우).
        manufacturer_country: 제조사 국가명.
        manufacturer_name: 제조사명.
        production_country: 제조 국가명 (제조 공장 국가).
        published_date: 공표일 (yyyyMMdd).
        recall_scope: 리콜 범위 (공표문상 리콜 수량 설명).
        recall_action_count: 리콜 조치 수량.
        recall_start_date: 리콜 시작일자.
        recall_end_date: 리콜 종료일자.
        defect_description: 제품 결함.
        hazard_description: 위해 정보.
        consumer_guidance: 소비자 행동요령.
        recall_images: 리콜 사진 목록.
    """

    model_config = ConfigDict(populate_by_name=True)

    recall_id: str | None = Field(None, alias="recallUid")
    recall_product_name: str | None = Field(None, alias="recallProductName")
    recall_brand_name: str | None = Field(None, alias="recallBrandName")
    recall_model_name: str | None = Field(None, alias="recallModelName")
    recall_model_count: int | None = Field(None, alias="recallModelCnt")
    recall_type: str | None = Field(None, alias="recallTypeName")
    recall_method: str | None = Field(None, alias="recallMeans")
    barcode_number: str | None = Field(None, alias="barcodeNum")
    category_name: str | None = Field(None, alias="categoryName")
    certification_number: str | None = Field(None, alias="certNum")
    product_group_name: str | None = Field(None, alias="productItemName")
    recall_company_type: str | None = Field(None, alias="recallCmpnyDivName")
    recall_contact_phone: str | None = Field(None, alias="recallInqryTel")
    recall_company_name: str | None = Field(None, alias="recallCmpnyName")
    recall_company_business_number: str | None = Field(None, alias="recallCmpnySsn")
    foreign_company_name: str | None = Field(None, alias="recallFrgnCmpnyName")
    manufacturer_country: str | None = Field(None, alias="makerCntryName")
    manufacturer_name: str | None = Field(None, alias="makerName")
    production_country: str | None = Field(None, alias="makingCntryName")
    published_date: str | None = Field(None, alias="publishDate")
    recall_scope: str | None = Field(None, alias="publishRecallVol")
    recall_action_count: str | None = Field(None, alias="recallActionAmt")
    recall_start_date: str | None = Field(None, alias="recallStaDate")
    recall_end_date: str | None = Field(None, alias="recallEndDate")
    # 같은 원문 키라도 국내·국외 API의 의미가 달라 명세 의미대로 이름 붙임
    defect_description: str | None = Field(None, alias="harmDscr")
    hazard_description: str | None = Field(None, alias="accidentCaseDscr")
    consumer_guidance: str | None = Field(None, alias="publishActionDscr")
    recall_images: list[RecallFile] | None = Field(None, alias="recallFiles")


class RecallSearchResponse(BaseModel):
    """국내리콜정보 조회 응답.

    Attributes:
        items: 리콜정보 목록.
    """

    items: list[RecallItem]


# -- 국외리콜 --

class ForeignRecallItem(BaseModel):
    """국외리콜정보 단건.

    Attributes:
        recall_id: 국외리콜 아이디.
        recall_model_name: 모델명.
        recall_model_count: 모델 개수.
        recall_product_name: 제품명.
        recall_brand_name: 상표명.
        manufacturer_name: 제조사명.
        production_country: 제조국 (예: 국외>아시아지역>중국).
        recall_type: 리콜종류 (자발적리콜, 권고에따른리콜, 명령에따른리콜).
        publishing_country: 리콜 공표 국가명.
        publishing_agency: 리콜 공표 기관명 (예: 영국 OPSS).
        recall_method: 리콜방법.
        hazard_description: 위해 내용.
        consumer_guidance: 소비자 행동요령.
        action_taken: 조치사항 (예: 소비자회수, 반품).
        product_description: 제품 설명.
        source_url: 리콜 공표 원문 URL.
        published_date: 공표일.
        registered_date: 등록일 (제품안전정보센터에 등록된 날).
        image_url: 이미지 URL (여러 장이면 쉼표 구분).
    """

    model_config = ConfigDict(populate_by_name=True)

    recall_id: str | None = Field(None, alias="fRecallUid")
    recall_model_name: str | None = Field(None, alias="recallModelName")
    recall_model_count: int | None = Field(None, alias="recallModelCnt")
    recall_product_name: str | None = Field(None, alias="recallProductName")
    recall_brand_name: str | None = Field(None, alias="recallBrandName")
    manufacturer_name: str | None = Field(None, alias="makerName")
    production_country: str | None = Field(None, alias="makingCntryName")
    recall_type: str | None = Field(None, alias="recallTypeName")
    publishing_country: str | None = Field(None, alias="recallPblshCntryName")
    publishing_agency: str | None = Field(None, alias="recallPblshOrgnName")
    recall_method: str | None = Field(None, alias="recallMeans")
    # 같은 원문 키라도 국내·국외 API의 의미가 달라 명세 의미대로 이름 붙임
    hazard_description: str | None = Field(None, alias="violateDscr")
    consumer_guidance: str | None = Field(None, alias="accidentCaseDscr")
    action_taken: str | None = Field(None, alias="publishActionDscr")
    product_description: str | None = Field(None, alias="recallProductDscr")
    source_url: str | None = Field(None, alias="recallUrl")
    published_date: str | None = Field(None, alias="publishDate")
    registered_date: str | None = Field(None, alias="signDttm")
    image_url: str | None = Field(None, alias="imageUrl")


class ForeignRecallSearchResponse(BaseModel):
    """국외리콜정보 조회 응답.

    Attributes:
        items: 국외리콜 목록.
    """

    items: list[ForeignRecallItem]
