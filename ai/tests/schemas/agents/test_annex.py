"""별표 파싱 에이전트 출력 스키마가 strict 구조화 출력에 쓸 수 있는 형태인지 확인한다."""

import pytest
from openai.lib._parsing._completions import type_to_response_format_param
from pydantic import ValidationError

from app.schemas.agents.annex import AnnexItem, AnnexParseOutput


def _item(**fields) -> dict:
    return {
        "category_path": ["2. 전기기기용스위치", "가. 스위치"],
        "item_label": "①",
        "item_name": "전기기기용 스위치",
        "conditions": ["정격전압 480V이하, 정격전류가 30A 이하인 것에 한정한다"],
        "exclusions": [],
        "inclusions": ["교류전원 30V 이하, 직류 전원 42V 이하에서 사용하는 것을 포함한다."],
        "attributes": [],
        "source_text": "① 전기기기용 스위치(정격전압 480V이하, 정격전류가 30A 이하인 것에 한정한다)",
        **fields,
    }


def test_strict_스키마로_변환되고_모든_필드가_필수다():
    response_format = type_to_response_format_param(AnnexParseOutput)["json_schema"]
    schema = response_format["schema"]

    assert response_format["strict"] is True
    assert schema["required"] == ["scheme", "items", "skipped", "notes"]
    assert schema["$defs"]["AnnexItem"]["required"] == list(AnnexItem.model_fields)


def test_표_전체_비고와_포함_문구를_담는다():
    output = AnnexParseOutput.model_validate({
        "scheme": "안전인증대상전기용품",
        "items": [_item()],
        "skipped": [{"item_label": "②", "reason": "삭제 <2023. 3. 20.>"}],
        "notes": ["1차 전지(건전지) 및 2차 전지(충전지)만을 전원으로 사용하는 구조의 것은 안전인증대상전기용품에서 제외한다."],
    })

    assert output.items[0].inclusions == ["교류전원 30V 이하, 직류 전원 42V 이하에서 사용하는 것을 포함한다."]
    assert output.notes[0].startswith("1차 전지")


def test_원문_번호가_없어도_키는_있어야_한다():
    with pytest.raises(ValidationError):
        AnnexItem.model_validate({key: value for key, value in _item().items() if key != "item_label"})

    assert AnnexItem.model_validate(_item(item_label=None)).item_label is None


def test_정의하지_않은_필드는_거부한다():
    with pytest.raises(ValidationError):
        AnnexItem.model_validate(_item(low_voltage_included=True))
