"""식약처 외부 API 응답 모델."""

from pydantic import BaseModel


# -- 의료기기 품목정보 --

class MedicalDeviceItem(BaseModel):
    """의료기기 품목정보 단건."""

    mdeq_prdlst_sn: str | None = None
    prdlst_nm: str | None = None
    meddev_item_no: str | None = None
    mdeq_clsf_no: str | None = None
    clsf_no_grad_cd: str | None = None
    type_info: str | None = None
    prmsn_ymd: str | None = None
    prmsn_dclr_divs_nm: str | None = None
    indt_nm: str | None = None
    use_purps_cont: str | None = None
    use_mth_cont: str | None = None
    attn_mttr_cont: str | None = None
    size_info: str | None = None
    chrtr_info: str | None = None
    mnft_mth_cont: str | None = None
    vld_prd_info: str | None = None
    test_stnd_cont: str | None = None
    mnft_clnt_nm: str | None = None
    mnsc_nm: str | None = None
    mnsc_natn_cd: str | None = None
    rtrcn_dsctn_divs_cd: str | None = None
    rtrcn_dsctn_dt: str | None = None
    inst_area_divs_nm: str | None = None
    prdt_nm_info: str | None = None


class MedicalDeviceResponse(BaseModel):
    """의료기기 품목정보 조회 응답.

    Attributes:
        total_count: 전체 건수.
        items: 의료기기 품목 목록.
    """

    total_count: int
    items: list[MedicalDeviceItem]


# -- 화장품 규제원료 --

class CosmeticsReglItem(BaseModel):
    """화장품 규제원료 단건."""

    ingr_std_name: str | None = None
    ingr_eng_name: str | None = None
    proh_national: str | None = None
    limit_national: str | None = None


class CosmeticsReglResponse(BaseModel):
    """화장품 규제원료 조회 응답.

    Attributes:
        total_count: 전체 건수.
        items: 규제 성분 목록.
    """

    total_count: int
    items: list[CosmeticsReglItem]
