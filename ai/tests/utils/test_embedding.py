"""임베딩 유틸 테스트. 가짜 임베딩 모델로 바꿔 실제 API는 호출하지 않는다."""

import asyncio

import langchain_openai
import pytest

from app import config
from app.utils import embedding

_SETTINGS = config.Settings(
    api_key="test-key",
    base_url="https://mlapi.run/example/v1",
    model="openai/gpt-4.1-mini",
    embedding_model="openai/text-embedding-3-small",
    database_url="",
    data_go_kr_key="test-data-key",
    safetykorea_key="test-safety-key",
    law_oc="test-oc",
)


class _FakeEmbeddings:
    """OpenAIEmbeddings 대역. 생성 인자와 입력 텍스트를 기록함."""

    instances: list["_FakeEmbeddings"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.inputs = None
        _FakeEmbeddings.instances.append(self)

    async def aembed_query(self, text):
        self.inputs = text
        return [0.1] * 1536

    async def aembed_documents(self, texts):
        self.inputs = texts
        return [[0.1] * 1536 for _ in texts]


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    _FakeEmbeddings.instances = []
    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", _FakeEmbeddings)


def test_임베딩_모델은_설정의_모델명과_접속정보로_만든다():
    model = embedding.build_embedding_model(_SETTINGS)

    assert model.kwargs == {
        "model": "openai/text-embedding-3-small",
        "base_url": "https://mlapi.run/example/v1",
        "api_key": "test-key",
    }


def test_설정을_넘기지_않으면_공용_설정을_쓴다(monkeypatch):
    monkeypatch.setattr(embedding, "get_settings", lambda: _SETTINGS)

    model = embedding.build_embedding_model()

    assert model.kwargs["model"] == "openai/text-embedding-3-small"


def test_단일_텍스트는_query_임베딩으로_변환한다():
    vector = asyncio.run(embedding.embed_text("헤어드라이어", _SETTINGS))

    assert len(vector) == 1536
    assert _FakeEmbeddings.instances[-1].inputs == "헤어드라이어"


def test_여러_텍스트는_document_임베딩으로_순서대로_변환한다():
    vectors = asyncio.run(embedding.embed_texts(["전기용품", "생활용품"], _SETTINGS))

    assert len(vectors) == 2
    assert _FakeEmbeddings.instances[-1].inputs == ["전기용품", "생활용품"]
