"""추출 에이전트 trace 기록: 판매자 구역 자르기, 모델 출력에서 코드가 바꾼 것."""

from app.agents.extraction import ExtractionAgent
from app.observability.trace import trace_run
from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes

_TITLE = "접이식 원목 의자 3단 높이 조절"


def test_기록_중이면_블록마다_쇼핑몰·자르기_여부·제목·글자_수_전후를_남긴다(stub_model, records, aliexpress_page, tmp_path):
    source = ExtractionInput(product_id="p-1", text_blocks=[aliexpress_page, "판매자가 붙여 넣은 설명"])

    with trace_run(tmp_path) as recorder:
        ExtractionAgent(stub_model(ProductAttributes())).run(source)

    first, second = recorder.info["seller_region"]
    assert (first["site"], first["trimmed"], first["title"]) == ("aliexpress", True, _TITLE)
    assert first["chars"][0] == len(aliexpress_page) and first["chars"][1] < first["chars"][0]
    assert second == {"site": None, "trimmed": False, "title": None, "chars": [13, 13]}


def test_기록_중이면_되돌린_false·되살린_제목·규칙이_더한_속성과_모순을_남긴다(stub_model, records, aliexpress_page,
                                                       tmp_path):
    reply = ProductAttributes(food_contact=False, listing_text=["판매자 설명 문장"])
    source = ExtractionInput(product_id="p-1",
                             text_blocks=[aliexpress_page, "MagSafe 1460mAh 케이스", "배터리 속성 배터리 미포함"])

    with trace_run(tmp_path) as recorder:
        ExtractionAgent(stub_model(reply)).run(source)

    post = recorder.info["postprocess"]
    assert post["guessed_false_to_none"] == ["food_contact"]
    assert post["titles_restored"] == [_TITLE]
    assert [(attribute["name"], attribute["value"]) for attribute in post["rule_attributes_added"]] == [
        ("배터리 용량", "1460mAh")]
    assert len(post["rule_conflicts_added"]) == 1 and "1460mAh" in post["rule_conflicts_added"][0]
    assert [call["component"] for call in recorder.info["calls"]] == ["extraction"]
