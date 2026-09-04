"""추출 에이전트의 출력이자 선택 에이전트의 입력인 상품 스키마."""

from __future__ import annotations

from pydantic import Field

from .base import StrictModel


# 재질·성분·주파수·정격처럼 고정 필드 외에 필요한 상품 속성.
# 예: name="재질", value="대나무". source_text와 source_url은 이 속성의 근거이다.
class Attribute(StrictModel):
    name: str
    value: str
    source_text: str | None = None
    source_url: str | None = None

# 상품 페이지에서 파싱한 사실
# 추출 담당자는 이 모델을 출력하고 선택 담당자는 같은 모델을 입력으로 사용한다.
# 모델은 입력 형식만 검사하며, 상품 특성을 자동으로 추출·판정하지는 않는다.
class Product(StrictModel):
    """상품 상세페이지에서 파싱해 툴 선택에 사용하는 정보."""

    # 필수 식별자. 상품 정보와 이후 심사 결과를 연결할 때 사용한다.
    product_id: str
    product_name: str | None = None
    category: str | None = None
    intended_use: str | None = None
    # "만 14세 이상", "36개월 이상" 같은 조건을 잃지 않도록 연령 원문을 보존한다.
    target_age: str | None = None

    # 툴 선택을 위한 상품 특성이다. 이 값만으로 규제 적용 여부를 확정하지 않는다.
    # True: 해당 특성 확인, False: 해당하지 않음을 확인, None: 정보 부족 또는 불명확.
    # 기존 상품 입력과 같이 생략한 필드는 None으로 처리한다.
    # 언급이 없다는 이유만으로 False를 채우지 않는다.
    # Field의 description은 설명이며, 그 문구대로 해석하는 로직은 별도로 구현해야 한다.
    electrical_powered: bool | None = Field(default=None, description="전기로 작동하는가")
    # 통신·충전·차폐는 별개 특성이며, 한 상품에서 동시에 True일 수도 있다.
    wireless_comm: bool | None = Field(
        default=None, description="전파를 주고받는가. 블루투스·WiFi·RF 리모컨"
    )
    wireless_charging: bool | None = Field(
        default=None, description="무선충전 기능이 있는가. Qi·자기유도·자기공명"
    )
    wireless_shield: bool | None = Field(
        default=None, description="전파를 막는가. RFID 차단·전자파 차폐"
    )
    # 전지가 포함된 기기인지, 판매 상품 자체가 전지인지 구분한다.
    battery_included: bool | None = Field(default=None, description="전지가 들어 있는가")
    battery_is_the_product: bool | None = Field(default=None, description="전지가 제품 자체인가")
    heating: bool | None = Field(default=None, description="발열이 기능인가. 부수적 발열은 false")
    food_contact: bool | None = Field(default=None, description="음식에 닿는가")
    skin_contact: bool | None = Field(default=None, description="피부·구강·점막에 닿는가")
    # 판매자가 표방하는 효과를 기록한다. 실제 효과가 입증됐다는 뜻은 아니다.
    medical_claim: bool | None = Field(default=None, description="질병명·신체기능 개선을 표방하는가")
    cosmetic_claim: bool | None = Field(default=None, description="미용·피부 효과를 표방하는가")
    weapon_like: bool | None = Field(default=None, description="총·칼·석궁·전자충격기 형태인가")
    plant_material: bool | None = Field(default=None, description="목재·대나무·등나무·짚·건조식물")
    chemical_product: bool | None = Field(
        default=None, description="세정·방향·살균이 주된 기능인가"
    )
    # 연령 원문과 광고 맥락을 해석한 선택 신호이며, target_age 원문을 대체하지 않는다.
    for_children: bool | None = Field(
        default=None,
        description=(
            "만 13세 이하 어린이가 사용 대상인가. "
            "연령 표기뿐 아니라 광고가 겨냥하는 실사용 연령으로 판단한다"
        ),
    )

    # 표시광고 검사 등에 쓸 상품 설명·홍보 문구의 원문.
    # default_factory=list는 상품마다 독립적인 빈 리스트를 만든다.
    listing_text: list[str] = Field(default_factory=list)
    # 추가 재질·성분·기능 등을 근거와 함께 담는다. 고정 필드를 임의로 늘리는 대신 활용한다.
    attributes: list[Attribute] = Field(default_factory=list)
    source_url: str | None = None
