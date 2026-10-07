"""관세청 클라이언트의 HS 정규화·검증을 실제 호출 없이 검증한다."""

import pytest
from pydantic import ValidationError

from app.clients.customs import CLIPClient
from app.schemas.clients.customs_request import CustomsGwConfirmationRequest


@pytest.mark.parametrize(
    "raw_hs",
    [
        "8414.59-9000",
        "<em>8414</em>.59-9000",
    ],
)
def test_CLIP_HS는_숫자_10자리로_정규화한다(raw_hs):
    # 점이 남으면 세관장확인이 오류 없이 0건을 돌려준다 (#182).
    case = CLIPClient()._parse_item({"DTRM_HS_SGN": raw_hs})

    assert case.hs_code == "8414599000"


def test_정규화된_CLIP_HS는_세관장확인_요청에_그대로_들어간다():
    case = CLIPClient()._parse_item({"DTRM_HS_SGN": "3307.49-0000"})

    request = CustomsGwConfirmationRequest(hs_code=case.hs_code)

    assert request.hs_code == "3307490000"


@pytest.mark.parametrize(
    "hs_code",
    [
        "8414.599000",
        "8414",
        "84145990001",
        "",
    ],
)
def test_숫자_10자리가_아닌_HS는_세관장확인_요청에서_거부한다(hs_code):
    with pytest.raises(ValidationError):
        CustomsGwConfirmationRequest(hs_code=hs_code)
