"""ExtractionAgent 입출력: 식별자 보존, 빈 입력 거부, 메시지 모양, 사용량 기록 이름."""

import contextlib

import pytest

from app.agents.base import AgentError
from app.agents.extraction import ExtractionAgent
from app.schemas.agent import ExtractionInput
from app.schemas.product import Product, ProductAttributes


def test_모델이_채운_상품_특성에_입력의_식별자와_출처가_합쳐진다(stub_model, records):
    # 모델은 상품 특성만 채움. 식별자·출처는 입력값 그대로
    agent = ExtractionAgent(stub_model(ProductAttributes(product_name="4채널 드론", wireless_comm=True)))
    source = ExtractionInput(
        product_id="prod-1", source_url="https://example.com/item/1", text_blocks=["4채널 무선 조종 드론입니다."],
    )

    result = agent.run(source)

    assert isinstance(result, Product)
    assert (result.product_id, result.source_url) == ("prod-1", "https://example.com/item/1")
    assert (result.product_name, result.wireless_comm) == ("4채널 드론", True)


def test_텍스트와_이미지가_모두_없으면_예외를_낸다(stub_model, records):
    with pytest.raises(ValueError):
        ExtractionAgent(stub_model(ProductAttributes())).run(ExtractionInput(product_id="prod-2"))


def test_글_없이_이미지만_있어도_추출한다(stub_model, records):
    # 상세 설명이 이미지뿐인 상품 (URL 입력에서 글을 못 얻은 경우)
    model = stub_model(ProductAttributes(product_name="선풍기"))

    result = ExtractionAgent(model).run(ExtractionInput(product_id="prod-img", image_urls=["https://img/spec.jpg"]))

    assert result.product_name == "선풍기"
    assert [part["type"] for part in model.received[0][-1].content] == ["image_url"]


def test_텍스트와_이미지가_하나의_사용자_메시지로_모델에_전달된다(stub_model, records):
    model = stub_model(ProductAttributes())
    # 로컬 이미지는 호출자가 data URI로 바꿔 넣음
    source = ExtractionInput(product_id="prod-3", text_blocks=["본문 텍스트"], image_urls=["data:image/png;base64,AAAA"])

    ExtractionAgent(model).run(source)

    assert [part["type"] for part in model.received[0][-1].content] == ["text", "image_url"]


def test_사용량은_상품_ID로_추출_이름에_기록한다(stub_model, records):
    ExtractionAgent(stub_model(ProductAttributes())).run(ExtractionInput(product_id="prod-10", text_blocks=["글"]))

    assert (records[0]["agent"], records[0]["subject_id"]) == ("extraction", "prod-10")


def test_평가_실행은_운영과_다른_이름으로_집계된다(stub_model, records):
    agent = ExtractionAgent(stub_model(ProductAttributes()), usage_agent="extraction-eval")

    agent.run(ExtractionInput(product_id="eval-1", text_blocks=["글"]))

    assert records[0]["agent"] == "extraction-eval"


def test_요청_본문은_상품_스키마_클래스를_넘길_때와_같다(fake_gateway, records):
    # 중첩 스키마(속성 목록)와 이미지 메시지가 SDK 변환 후에도 같은 요청인지 확인
    source = ExtractionInput(
        product_id="prod-req", text_blocks=["USB 충전식 선풍기"], image_urls=["data:image/png;base64,AAA"],
    )
    actual: list[dict] = []
    agent = ExtractionAgent(fake_gateway("{}", "stop", actual))
    expected: list[dict] = []
    reference = fake_gateway("{}", "stop", expected).with_structured_output(ProductAttributes, include_raw=True)

    with contextlib.suppress(Exception):
        reference.invoke(agent._build_messages(source))
    with contextlib.suppress(AgentError):
        agent.run(source)

    assert actual == expected
