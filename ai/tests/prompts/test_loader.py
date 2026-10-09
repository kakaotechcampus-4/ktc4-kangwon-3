"""공용 프롬프트 로더의 스냅샷·지문·캐시·호환 인터페이스(#171 §3)를 확인한다."""

import hashlib

import pytest

from app.eval.runner import prompt_fingerprint
from app.prompts import (
    PromptName,
    clear_prompt_cache,
    fingerprint,
    get_prompt,
    load_prompt,
    normalize_newlines,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_prompt_cache()
    yield
    clear_prompt_cache()


@pytest.mark.parametrize("name", list(PromptName))
def test_본문과_지문은_같은_스냅샷에서_나온다(name):
    snapshot = get_prompt(name)

    assert snapshot.name is name
    assert snapshot.path.name == f"{name.value}.md"
    assert snapshot.text
    assert snapshot.sha256 == hashlib.sha256(snapshot.text.encode("utf-8")).hexdigest()
    assert len(snapshot.sha256) == 64


@pytest.mark.parametrize("text", ["가\r\n나\r\n", "가\r나\r", "가\n나\n"])
def test_줄바꿈이_달라도_같은_지문을_낸다(text):
    assert normalize_newlines(text) == "가\n나\n"
    assert fingerprint(text) == fingerprint("가\n나\n")


@pytest.mark.parametrize("name", list(PromptName))
def test_기존_평가_러너_지문과_같다(name):
    snapshot = get_prompt(name)

    assert snapshot.sha256 == prompt_fingerprint(snapshot.path)


def test_같은_이름은_한_번만_읽고_초기화하면_다시_읽는다():
    first = get_prompt(PromptName.EXTRACTION)

    assert get_prompt(PromptName.EXTRACTION) is first

    clear_prompt_cache()

    reloaded = get_prompt(PromptName.EXTRACTION)
    assert reloaded is not first
    assert reloaded == first


def test_load_prompt는_스냅샷_본문을_돌려준다():
    assert load_prompt("selection") == get_prompt(PromptName.SELECTION).text


def test_load_prompt는_등록하지_않은_이름을_거부한다():
    with pytest.raises(ValueError, match="등록하지 않은 프롬프트입니다."):
        load_prompt("unknown")
