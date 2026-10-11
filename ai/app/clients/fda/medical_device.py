"""식약처 의료기기 품목정보 클라이언트.

역할
    의료기기 품목(분류번호·등급·허가일·제조사·사용목적 등)을 페이지 단위로 조회.
    검색 조건 없이 전체 목록을 주는 API라 DB 적재용으로 사용.
"""

import httpx

from .base import FdaBaseClient
from ...schemas.clients.fda_response import MedicalDeviceItem, MedicalDeviceResponse


class MedicalDeviceClient(FdaBaseClient[MedicalDeviceResponse]):
    """의료기기 품목정보 조회 클라이언트. 응답이 items[].item 중첩 구조."""

    _ENDPOINT = "/1471000/MdeqPrdlstInfoService02/getMdeqPrdlstInfoInq02"

    def _parse(self, raw: httpx.Response) -> MedicalDeviceResponse:
        """의료기기 품목정보 JSON 원문을 응답 스키마로 변환한다.

        Args:
            raw: `_send`가 받은 JSON 원문 응답.

        Returns:
            MedicalDeviceResponse: 의료기기 품목 목록.
        """
        body = self._parse_body(raw)
        raw_items = body.get("items", [])
        # 의료기기는 items[].item 중첩 구조
        items = [
            self._parse_item(entry["item"])
            for entry in raw_items
            if isinstance(entry, dict) and "item" in entry
        ]
        return MedicalDeviceResponse(
            total_count=body.get("totalCount", 0),
            items=items,
        )

    def _parse_item(self, item: dict) -> MedicalDeviceItem:
        """의료기기 품목 원문 항목 하나를 스키마로 변환한다.

        Args:
            item: 원문 items[].item 항목.

        Returns:
            MedicalDeviceItem: 풀어 쓴 필드 이름으로 옮긴 항목.
        """
        return MedicalDeviceItem(
            item_serial_number=item.get("MDEQ_PRDLST_SN"),              # 품목일련번호
            item_name=item.get("PRDLST_NM"),                            # 품목명
            approval_number=item.get("MEDDEV_ITEM_NO"),                 # 품목 허가·인증·신고 번호
            classification_number=item.get("MDEQ_CLSF_NO"),             # 분류번호
            grade=item.get("CLSF_NO_GRAD_CD"),                          # 등급
            model_names=item.get("TYPE_INFO"),                          # 모델명
            approval_date=item.get("PRMSN_YMD"),                        # 허가일자
            approval_type=item.get("PRMSN_DCLR_DIVS_NM"),               # 허가·인증·신고 구분
            business_type=item.get("INDT_NM"),                          # 업종
            intended_use=item.get("USE_PURPS_CONT"),                    # 사용목적
            usage_method=item.get("USE_MTH_CONT"),                      # 사용방법
            precautions=item.get("ATTN_MTTR_CONT"),                     # 주의사항
            size=item.get("SIZE_INFO"),                                 # 크기
            characteristics=item.get("CHRTR_INFO"),                     # 특성
            manufacturing_method=item.get("MNFT_MTH_CONT"),             # 제조방법
            validity_period=item.get("VLD_PRD_INFO"),                   # 유효기간
            test_standard=item.get("TEST_STND_CONT"),                   # 시험규격
            manufacturing_client_name=item.get("MNFT_CLNT_NM"),         # 제조의뢰자
            manufacturer_name=item.get("MNSC_NM"),                      # 제조원
            manufacture_country=item.get("MNSC_NATN_CD"),               # 제조국 (국가명으로 옴)
            cancellation_type_code=item.get("RTRCN_DSCTN_DIVS_CD"),     # 취소·취하 구분코드
            cancellation_date=item.get("RTRCN_DSCTN_DT"),               # 취소·취하일자
            jurisdiction_name=item.get("INST_AREA_DIVS_NM"),            # 관할 기관
            product_name=item.get("PRDT_NM_INFO"),                      # 제품명
        )
