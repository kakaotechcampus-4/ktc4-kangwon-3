"""수집 실험 러너의 저장·비교 함수를 모델·네트워크 없이 확인한다."""

import json

from app.eval.collect_runner import (
    MAX_ALL_IMAGES,
    compare_fields,
    image_sourced_attributes,
    mode_input,
    product_key,
    usage_of,
    write_summary,
)
from app.pipeline.url_source import UrlSource
from app.schemas.agent import ExtractionInput, ImageTriageResponse
from app.schemas.clients.marketplace_response import ProductPage, ProductPageImage

URL = "https://seller.en.made-in-china.com/product/jZbflYzyZctU/China-Power-Bank.html"


def _source(image_count: int = 3) -> UrlSource:
    images = [ProductPageImage(url=f"https://img/{n}.jpg", thumbnail_url=f"https://img/{n}-s.jpg", area="description")
              for n in range(image_count)]
    page = ProductPage(source_url=URL, site="made_in_china", title="보조배터리", text_blocks=["Capacity: 10000mAh"],
                       images=images)
    return UrlSource(page=page, triage=ImageTriageResponse(items=[]), selected=images[:1],
                     extraction_input=ExtractionInput(product_id="p", source_url=URL, text_blocks=page.text_blocks,
                                                      image_urls=[images[0].url]))


def test_저장_폴더는_Made_in_China_상품_ID나_경로_끝으로_정한다():
    assert product_key(URL) == "jZbflYzyZctU"
    assert product_key("https://example.com/item/a b?c.html") == "a_b"


def test_방식마다_판매자_글은_같고_이미지만_다르다():
    source = _source()

    inputs = {mode: mode_input(source, mode, f"s-{mode}") for mode in ("text", "all", "selected")}

    assert {mode: value.image_urls for mode, value in inputs.items()} == {
        "text": [], "all": ["https://img/0.jpg", "https://img/1.jpg", "https://img/2.jpg"],
        "selected": ["https://img/0.jpg"]}
    assert {value.product_id for value in inputs.values()} == {"s-text", "s-all", "s-selected"}
    assert all(value.text_blocks == ["Capacity: 10000mAh"] for value in inputs.values())


def test_all_방식은_상한까지만_넣는다():
    assert len(mode_input(_source(MAX_ALL_IMAGES + 5), "all", "s").image_urls) == MAX_ALL_IMAGES


def test_판매자_글에_없는_근거의_속성만_고른다():
    product = {"attributes": [
        {"name": "용량", "value": "10000mAh", "source_text": "capacity:  10000MAH"},  # 공백·대소문자만 다름
        {"name": "보호회로", "value": "과충전 보호", "source_text": "Overcharge protection"},
        {"name": "색상", "value": "흰색", "source_text": None},
    ]}

    assert [a["name"] for a in image_sourced_attributes(product, ["Capacity: 10000mAh"])] == ["보호회로"]


def test_값이_하나라도_다른_판단_칸만_모은다():
    results = {
        "text": [{"heating": False, "wireless_charging": None, "listing_text": ["a"]}, None],
        "selected": [{"heating": False, "wireless_charging": True, "listing_text": ["b"]}],
    }

    assert compare_fields(results) == [
        ("heating", {"text": [False, "실패"], "selected": [False]}),
        ("wireless_charging", {"text": [None, "실패"], "selected": [True]}),
    ]


def test_대상_ID별로_사용량을_합친다(tmp_path):
    log = tmp_path / "usage.jsonl"
    log.write_text("\n".join([
        json.dumps({"subject_id": "s-1", "input_tokens": 100, "output_tokens": 10, "estimated_cost_krw": 0.5}),
        json.dumps({"subject_id": "s-2", "input_tokens": 999}),
        "깨진 줄",
        json.dumps({"subject_id": "s-1", "input_tokens": 50, "output_tokens": None, "estimated_cost_krw": 0.25}),
    ]), encoding="utf-8")

    assert usage_of("s-1", log) == {"calls": 2, "input_tokens": 150, "output_tokens": 10, "estimated_cost_krw": 0.75}


def test_저장된_결과로_요약을_만든다(tmp_path):
    source = _source()
    (tmp_path / "page.json").write_text(source.page.model_dump_json(), encoding="utf-8")
    usage = {"calls": 1, "input_tokens": 10, "output_tokens": 1, "estimated_cost_krw": 0.1, "seconds": 1.0}
    (tmp_path / "meta.json").write_text(json.dumps({
        "url": URL, "triage": usage,
        "modes": {"text": [{"run": 1, "images": 0, **usage}], "selected": [{"run": 1, "images": 1, **usage}]},
    }), encoding="utf-8")
    products = {
        "text": {"for_children": None, "attributes": []},
        "selected": {"for_children": True, "attributes": [
            {"name": "연령", "value": "3+", "source_text": "Age 3+"}]},
    }
    for mode, product in products.items():
        (tmp_path / mode / "run_1").mkdir(parents=True)
        (tmp_path / mode / "run_1" / "product.json").write_text(json.dumps(product), encoding="utf-8")

    summary = write_summary(tmp_path).read_text(encoding="utf-8")

    assert "| for_children | null | true |" in summary
    assert "selected 1회: **연령** = 3+ (근거: Age 3+)" in summary
    assert "| selected | 1 | 1 |" in summary
