"""ExtractionAgent 동작 검증. 실제 OpenAI 호출 없이 모델을 스텁으로 대체한다."""

import pytest

from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes, Product
from app.agents.extraction import ExtractionAgent, ExtractionFailedError, _default_model


class _StubChatModel:
    """with_structured_output(...).invoke(...) 인터페이스만 흉내 낸 테스트 전용 스텁."""

    def __init__(self, result: ProductAttributes) -> None:
        self._result = result
        self.received_messages: list | None = None

    def with_structured_output(self, schema: type) -> "_StubChatModel":
        assert schema is ProductAttributes
        return self

    def invoke(self, messages: list) -> ProductAttributes:
        self.received_messages = messages
        return self._result


def test_모델이_채운_상품_특성에_입력의_식별자와_출처가_합쳐진다():
    # Given: 모델은 상품 특성만 채우고 식별자·출처는 모른다.
    stub_result = ProductAttributes(product_name="4채널 드론", wireless_comm=True)
    agent = ExtractionAgent(model=_StubChatModel(stub_result))
    source = ExtractionInput(
        product_id="prod-1",
        source_url="https://example.com/item/1",
        text_blocks=["4채널 무선 조종 드론입니다."],
    )

    # When
    result = agent.extract(source)

    # Then: 식별자·출처는 모델 출력이 아니라 입력값 그대로다.
    assert isinstance(result, Product)
    assert result.product_id == "prod-1"
    assert result.source_url == "https://example.com/item/1"
    assert result.product_name == "4채널 드론"
    assert result.wireless_comm is True


def test_텍스트와_이미지가_모두_없으면_예외를_낸다():
    agent = ExtractionAgent(model=_StubChatModel(ProductAttributes()))
    source = ExtractionInput(product_id="prod-2")

    with pytest.raises(ValueError):
        agent.extract(source)


def test_텍스트와_이미지가_하나의_사용자_메시지로_모델에_전달된다():
    stub_model = _StubChatModel(ProductAttributes())
    agent = ExtractionAgent(model=stub_model)
    source = ExtractionInput(
        product_id="prod-3",
        text_blocks=["본문 텍스트"],
        # 로컬 테스트 이미지는 data URI로 인코딩해서 넣는다(호출자 책임).
        image_urls=["data:image/png;base64,AAAA"],
    )

    agent.extract(source)

    assert stub_model.received_messages is not None
    human_message = stub_model.received_messages[-1]
    content_types = [part["type"] for part in human_message.content]
    assert content_types == ["text", "image_url"]


class _RaisingChatModel:
    """모델 호출 실패(레이트리밋·인증 오류 등)를 흉내 낸다."""

    def with_structured_output(self, schema: type) -> "_RaisingChatModel":
        return self

    def invoke(self, messages: list) -> ProductAttributes:
        raise RuntimeError("rate limit exceeded")


def test_모델_호출이_실패하면_ExtractionFailedError로_감싸진다():
    agent = ExtractionAgent(model=_RaisingChatModel())
    source = ExtractionInput(product_id="prod-4", text_blocks=["아무 텍스트"])

    with pytest.raises(ExtractionFailedError) as exc_info:
        agent.extract(source)

    # 원인 예외가 삼켜지지 않고 __cause__에 그대로 남아야 traceback으로 근본 원인을 찾을 수 있다.
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "rate limit exceeded" in str(exc_info.value.__cause__)


def test_default_model이_환경변수의_모델명과_base_url을_그대로_전달한다(monkeypatch):
    captured: dict = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    # 로컬 .env 파일 내용과 무관하게 이 테스트가 항상 같은 결과를 내도록 dotenv 로드를 무력화한다.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api-cloud-function.elice.io/v1")

    _default_model()

    assert captured["model"] == "openai/gpt-4.1-mini"
    assert captured["base_url"] == "https://api-cloud-function.elice.io/v1"


def test_default_model이_환경변수가_없으면_카탈로그_기본값을_쓴다(monkeypatch):
    captured: dict = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", _FakeChatOpenAI)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    _default_model()

    # 2026-09-06 확인: 엘리스 MLAPI 카탈로그 등록명("openai/" 접두어 포함)이 기본값이어야 한다.
    assert captured["model"] == "openai/gpt-4.1-mini"
    assert captured["base_url"] is None
