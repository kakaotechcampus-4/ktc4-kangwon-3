"""BaseAgent 가드레일: 표시한 에이전트만 시스템 프롬프트 뒤에 붙이고, 지문·생성 실패까지 확인한다."""

import hashlib

import pytest

import app.agents.base.guardrail as guardrail_module
from app.agents.base.guardrail import clear_guardrail_cache, get_guardrail
from app.prompts import PromptName, get_prompt


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_guardrail_cache()
    yield
    clear_guardrail_cache()


@pytest.fixture
def guarded(fakes):
    """가드레일을 쓰는 가짜 에이전트 클래스."""
    return type("GuardedAgent", (fakes.Agent,), {"uses_guardrail": True})


@pytest.fixture
def guarded_rules_only(fakes):
    """모델 없이 만드는 가드레일 에이전트 클래스 (프롬프트·메시지만 볼 때)."""
    return type("GuardedRulesOnlyAgent", (fakes.RulesOnly,), {"uses_guardrail": True})


def test_표시한_에이전트는_시스템_프롬프트_뒤에_가드레일을_빈_줄로_붙인다(guarded_rules_only):
    original = get_prompt(PromptName.EXTRACTION)

    prompt = guarded_rules_only().prompt
    [system, _] = guarded_rules_only()._messages("상품 설명")

    assert prompt.text == original.text.rstrip("\n") + "\n\n" + get_guardrail(PromptName.EXTRACTION).text
    assert system.content == prompt.text
    assert (prompt.name, prompt.path) == (original.name, original.path)


def test_가드레일을_붙이면_지문도_합친_본문으로_바뀐다(guarded_rules_only):
    prompt = guarded_rules_only().prompt

    assert prompt.sha256 == hashlib.sha256(prompt.text.encode("utf-8")).hexdigest()
    assert prompt.sha256 != get_prompt(PromptName.EXTRACTION).sha256


def test_실행_정보의_프롬프트_지문은_가드레일을_붙인_본문_기준이다(guarded, fakes, stub_model, records):
    outcome = guarded(stub_model(fakes.Answer(value="ok"))).run_with_meta(fakes.question)

    assert outcome.meta.prompt_sha256 == guarded(stub_model()).prompt.sha256


def test_표시하지_않은_에이전트는_가드레일을_붙이지_않는다(fakes):
    assert fakes.RulesOnly().prompt is get_prompt(PromptName.EXTRACTION)


def test_표시했는데_공통_가드레일_문서가_없으면_생성_때_실패한다(guarded_rules_only, fakes, tmp_path, monkeypatch):
    monkeypatch.setattr(guardrail_module, "COMMON_GUARDRAIL_PATH", tmp_path / "없음.md")

    with pytest.raises(FileNotFoundError):
        guarded_rules_only()
    fakes.RulesOnly()


def test_모델_없이_클래스로_구한_시스템_프롬프트는_에이전트가_보내는_것과_같다(guarded_rules_only, fakes):
    assert guarded_rules_only.system_prompt() == guarded_rules_only().prompt
    assert fakes.RulesOnly.system_prompt() is get_prompt(PromptName.EXTRACTION)
