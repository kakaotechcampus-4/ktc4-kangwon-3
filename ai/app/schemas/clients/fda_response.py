"""식약처 외부 API 응답 모델."""

from pydantic import BaseModel


# -- 의료기기 품목정보 --

class MedicalDeviceItem(BaseModel):
    """의료기기 품목정보 단건.

    Attributes:
        item_serial_number: 품목일련번호.
        item_name: 품목명 (분류상 이름, 예: 안경렌즈).
        approval_number: 품목 허가·인증·신고 번호 (예: 수허 06-652 호).
        classification_number: 분류번호 (예: A77010.01).
        grade: 등급 (1~4).
        model_names: 모델명 (예: HA-01S외 26건).
        approval_date: 허가일자.
        approval_type: 허가·인증·신고 구분.
        business_type: 업종 (제조업, 수입업).
        intended_use: 사용목적.
        usage_method: 사용방법.
        precautions: 사용 시 주의사항.
        size: 크기.
        characteristics: 특성(성능).
        manufacturing_method: 제조방법.
        validity_period: 유효기간.
        test_standard: 시험규격.
        manufacturing_client_name: 제조의뢰자.
        manufacturer_name: 제조원.
        manufacture_country: 제조국 (코드가 아닌 국가명으로 옴).
        cancellation_type_code: 취소·취하 구분코드. 값별 의미는 공개 명세에 없음.
        cancellation_date: 취소·취하일자. 값이 있으면 취소·취하된 품목.
        jurisdiction_name: 관할 기관 (예: 서울청, 식약처).
        product_name: 제품명 (상표명).
    """

    item_serial_number: str | None = None
    item_name: str | None = None
    approval_number: str | None = None
    classification_number: str | None = None
    grade: str | None = None
    model_names: str | None = None
    approval_date: str | None = None
    approval_type: str | None = None
    business_type: str | None = None
    intended_use: str | None = None
    usage_method: str | None = None
    precautions: str | None = None
    size: str | None = None
    characteristics: str | None = None
    manufacturing_method: str | None = None
    validity_period: str | None = None
    test_standard: str | None = None
    manufacturing_client_name: str | None = None
    manufacturer_name: str | None = None
    manufacture_country: str | None = None
    cancellation_type_code: str | None = None
    cancellation_date: str | None = None
    jurisdiction_name: str | None = None
    product_name: str | None = None


class MedicalDeviceResponse(BaseModel):
    """의료기기 품목정보 조회 응답.

    Attributes:
        total_count: 전체 건수.
        items: 의료기기 품목 목록.
    """

    total_count: int
    items: list[MedicalDeviceItem]


# -- 화장품 규제원료 --

class CosmeticsRegulationItem(BaseModel):
    """화장품 규제원료 단건.

    Attributes:
        ingredient_name: 원료 표준명.
        ingredient_english_name: 원료 영문명.
        prohibited_countries: 사용 금지 국가.
        restricted_countries: 사용 한도(제한) 국가.
    """

    ingredient_name: str | None = None
    ingredient_english_name: str | None = None
    prohibited_countries: str | None = None
    restricted_countries: str | None = None


class CosmeticsRegulationResponse(BaseModel):
    """화장품 규제원료 조회 응답.

    Attributes:
        total_count: 전체 건수.
        items: 규제 성분 목록.
    """

    total_count: int
    items: list[CosmeticsRegulationItem]
