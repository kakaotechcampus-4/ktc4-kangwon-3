"""ExtractionAgent 동작 검증. 실제 OpenAI 호출 없이 모델을 스텁으로 대체한다."""

import logging
from types import SimpleNamespace

import pytest

from app.schemas.agent import ExtractionInput
from app.schemas.product import ProductAttributes, Product
from app.agents.extraction import ExtractionAgent, ExtractionFailedError, _default_model

_FAKE_USAGE = {
    "input_tokens": 4000,
    "output_tokens": 500,
    "total_tokens": 4500,
    "input_token_details": {"cache_read": 2200},
}


class _StubChatModel:
    """with_structured_output(..., include_raw=True).invoke(...) 인터페이스만 흉내 낸 스텁."""

    def __init__(self, result: ProductAttributes | None, parsing_error: Exception | None = None) -> None:
        self._result = result
        self._parsing_error = parsing_error
        self.received_messages: list | None = None

    def with_structured_output(self, schema: type, include_raw: bool = False) -> "_StubChatModel":
        assert schema is ProductAttributes
        assert include_raw is True
        return self

    def invoke(self, messages: list) -> dict:
        self.received_messages = messages
        return {
            "raw": SimpleNamespace(usage_metadata=_FAKE_USAGE, response_metadata={}),
            "parsed": self._result,
            "parsing_error": self._parsing_error,
        }


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

    def with_structured_output(self, schema: type, include_raw: bool = False) -> "_RaisingChatModel":
        return self

    def invoke(self, messages: list) -> dict:
        raise RuntimeError("rate limit exceeded")


def test_모델_응답이_스키마와_안_맞으면_ExtractionFailedError를_낸다():
    # include_raw=True에서는 스키마 불일치가 예외가 아니라 parsing_error로 돌아온다.
    stub_model = _StubChatModel(result=None, parsing_error=ValueError("field required"))
    agent = ExtractionAgent(model=stub_model)
    source = ExtractionInput(product_id="prod-8", text_blocks=["아무 텍스트"])

    with pytest.raises(ExtractionFailedError) as exc_info:
        agent.extract(source)

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_토큰_사용량과_캐시_적용량이_로그에_남는다(caplog):
    agent = ExtractionAgent(model=_StubChatModel(ProductAttributes()))
    source = ExtractionInput(product_id="prod-9", text_blocks=["아무 텍스트"])

    with caplog.at_level(logging.INFO, logger="app.agents.extraction"):
        agent.extract(source)

    assert "input=4000" in caplog.text
    assert "cache_read=2200" in caplog.text
    assert "output=500" in caplog.text


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


def test_규칙_기반_모순이_LLM_결과와_합쳐져_Product_conflicts에_담긴다():
    # Given: LLM은 아무 모순도 못 봤다고 답하지만(빈 conflicts), 원문엔 파워뱅크 케이스와
    # 같은 패턴(용량 표기 + 배터리 미포함 문구)이 있다.
    stub_result = ProductAttributes(product_name="MagSafe 케이스")
    agent = ExtractionAgent(model=_StubChatModel(stub_result))
    source = ExtractionInput(
        product_id="prod-5",
        text_blocks=["MagSafe 1460mAh 케이스", "배터리 속성 배터리 미포함"],
    )

    result = agent.extract(source)

    # Then: LLM이 놓쳤어도 규칙 레이어가 잡아서 conflicts에 남는다.
    assert len(result.conflicts) == 1
    assert "1460mAh" in result.conflicts[0]
    # 그리고 정규식이 뽑은 값도 attributes에 들어간다.
    assert any(a.name == "배터리 용량" and a.value == "1460mAh" for a in result.attributes)


def test_규칙_값이_다른_속성값의_부분문자열이어도_버려지지_않는다():
    # Given: LLM이 뽑은 "모델번호" 속성값 안에 우연히 "220V"라는 문자열이 들어 있다.
    # (예전엔 부분 문자열 비교 때문에 이런 경우 진짜 정격전압 항목이 통째로 버려졌다)
    stub_result = ProductAttributes(
        attributes=[
            {"name": "모델번호", "value": "AC-220V-A1", "source_text": None, "source_url": None}
        ]
    )
    agent = ExtractionAgent(model=_StubChatModel(stub_result))
    source = ExtractionInput(product_id="prod-7", text_blocks=["정격전압 220V, 모델번호 AC-220V-A1"])

    result = agent.extract(source)

    # Then: 서로 다른 속성이므로 둘 다 남아야 한다.
    assert any(a.name == "모델번호" and a.value == "AC-220V-A1" for a in result.attributes)
    assert any(a.name == "정격전압" and a.value == "220V" for a in result.attributes)


def test_LLM이_이미_뽑은_값과_겹치는_규칙_결과는_중복으로_안_넣는다():
    stub_result = ProductAttributes(
        attributes=[
            {"name": "인증정보", "value": "CE-RoHS; CE-EMC(Electric)", "source_text": None, "source_url": None}
        ]
    )
    agent = ExtractionAgent(model=_StubChatModel(stub_result))
    source = ExtractionInput(product_id="prod-6", text_blocks=["인증정보: CE-RoHS; CE-EMC(Electric)"])

    result = agent.extract(source)

    # LLM이 이미 담아둔 것과 겹치므로 규칙이 같은 값을 또 추가하지 않는다.
    assert len(result.attributes) == 1
