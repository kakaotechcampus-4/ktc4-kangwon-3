"""공용 프롬프트 로더 테스트. 캐시와 프롬프트 지문을 확인한다."""

from pathlib import Path

import pytest

from app import prompts
from app.eval.runner import prompt_fingerprint as runner_prompt_fingerprint

_NAMES = ("extraction", "selection", "verification")


@pytest.fixture(autouse=True)
def _clear_prompt_cache():
    prompts.load_prompt.cache_clear()
    yield
    prompts.load_prompt.cache_clear()


@pytest.mark.parametrize("name", _NAMES)
def test_로더_지문은_평가_러너가_기록하던_지문과_같다(name):
    path = Path(prompts.__file__).with_name(f"{name}.md")

    assert prompts.prompt_fingerprint(name) == runner_prompt_fingerprint(path)


def test_줄바꿈만_다르면_지문이_같다():
    assert prompts.fingerprint_text("가\r\n나\r\n") == prompts.fingerprint_text("가\n나\n")


def test_내용이_한_글자라도_다르면_지문이_다르다():
    assert prompts.fingerprint_text("가\n나") != prompts.fingerprint_text("가\n다")


def test_같은_프롬프트는_파일을_한_번만_읽는다(monkeypatch):
    reads: list[Path] = []
    original_read_text = Path.read_text

    def counting_read_text(self, *args, **kwargs):
        reads.append(self)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)

    first = prompts.load_prompt("selection")
    second = prompts.load_prompt("selection")
    prompts.prompt_fingerprint("selection")

    assert first is second
    assert len(reads) == 1


def test_지문은_모델에_보내는_캐시된_원문으로_계산한다(monkeypatch):
    sent = prompts.load_prompt("selection")
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: "파일이 바뀐 뒤 내용")

    assert prompts.prompt_fingerprint("selection") == prompts.fingerprint_text(sent)


def test_등록하지_않은_이름은_ValueError():
    with pytest.raises(ValueError, match="등록하지 않은 프롬프트"):
        prompts.load_prompt("unknown")
