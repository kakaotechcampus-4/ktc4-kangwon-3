"""가드레일 문서 로더의 위치 규칙·이어 붙이기·캐시를 확인한다."""

import pytest

import app.agents.base.guardrail as guardrail_module
from app.agents.base.guardrail import (
    COMMON_GUARDRAIL_PATH,
    clear_guardrail_cache,
    extra_guardrail_path,
    get_guardrail,
)
from app.prompts import PromptName


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_guardrail_cache()
    yield
    clear_guardrail_cache()


@pytest.fixture
def docs(tmp_path, monkeypatch):
    """공통 문서와 에이전트 프롬프트를 임시 폴더로 바꿈. 추가 문서는 테스트가 만듦."""
    common = tmp_path / "guardrail.md"
    common.write_text("공통 규칙\n", encoding="utf-8")
    prompt = tmp_path / "agent" / "prompt.md"
    prompt.parent.mkdir()
    prompt.write_text("프롬프트\n", encoding="utf-8")
    monkeypatch.setattr(guardrail_module, "COMMON_GUARDRAIL_PATH", common)
    monkeypatch.setattr(guardrail_module, "prompt_path", lambda name: prompt)
    return common, prompt.with_name("guardrail.md")


@pytest.mark.parametrize(("name", "location"), [
    (PromptName.EXTRACTION, "agents/extraction/guardrail.md"),
    (PromptName.SELECTION, "agents/selection/guardrail.md"),
    (PromptName.ADVERTISING, "prompts/advertising.guardrail.md"),
    (PromptName.CHILDREN_FACTS, "prompts/children/facts.guardrail.md"),
])
def test_추가_문서는_프롬프트_옆에서_찾는다(name, location):
    assert extra_guardrail_path(name).as_posix().endswith(f"/app/{location}")


def test_공통_문서는_저장소에_있다():
    assert COMMON_GUARDRAIL_PATH.is_file()
    assert get_guardrail(PromptName.EXTRACTION).text.strip()


def test_추가_문서가_없으면_공통_문서만_쓴다(docs):
    common, _ = docs

    snapshot = get_guardrail(PromptName.EXTRACTION)

    assert snapshot.paths == (common,)
    assert snapshot.text == "공통 규칙\n"


def test_추가_문서가_있으면_공통_문서_뒤에_빈_줄로_잇는다(docs):
    common, extra = docs
    extra.write_text("\r\n추가 규칙\r\n\r\n", encoding="utf-8")

    snapshot = get_guardrail(PromptName.EXTRACTION)

    assert snapshot.paths == (common, extra)
    assert snapshot.text == "공통 규칙\n\n추가 규칙\n"


def test_공통_문서가_없으면_실패하고_실패는_캐시하지_않는다(docs):
    common, _ = docs
    common.unlink()

    with pytest.raises(FileNotFoundError):
        get_guardrail(PromptName.EXTRACTION)

    common.write_text("공통 규칙\n", encoding="utf-8")
    assert get_guardrail(PromptName.EXTRACTION).text == "공통 규칙\n"


def test_같은_이름은_한_번만_읽고_초기화하면_다시_읽는다(docs):
    common, _ = docs
    first = get_guardrail(PromptName.EXTRACTION)
    common.write_text("바뀐 규칙\n", encoding="utf-8")

    assert get_guardrail(PromptName.EXTRACTION) is first

    clear_guardrail_cache()

    assert get_guardrail(PromptName.EXTRACTION).text == "바뀐 규칙\n"
