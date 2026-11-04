"""에이전트 시스템 프롬프트 뒤에 붙이는 가드레일 문서 로더.

공통 문서 ``app/agents/base/guardrail.md`` 뒤에 에이전트별 고유 문서를 이어 붙임. 둘 다 필수.
    - 에이전트 패키지 프롬프트 ``agents/<이름>/prompt.md`` → 같은 폴더 ``guardrail.md``
    - Tool 안 단계 프롬프트 ``<Tool>/<단계>`` → ``tools/<Tool>/<단계>.guardrail.md``
    - Tool 하나에 프롬프트 하나 ``<Tool>`` → ``tools/<Tool>/guardrail.md``
"""

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from ...prompts import PromptName, PromptSnapshot, fingerprint, normalize_newlines, prompt_path

COMMON_GUARDRAIL_PATH = Path(__file__).parent / "guardrail.md"
# Tool 프롬프트는 아직 app/prompts에 있어 에이전트별 문서는 Tool 폴더에 둠 (app/prompts는 늘리지 않음)
_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"


@dataclass(frozen=True)
class GuardrailSnapshot:
    """한 시점에 읽은 가드레일 본문.

    Attributes:
        name: 붙일 에이전트의 프롬프트 이름.
        paths: 읽은 문서 경로. 공통 문서, 에이전트별 문서 순.
        text: 줄바꿈을 LF로 맞추고 문서 사이를 빈 줄로 이은 본문.
    """

    name: PromptName
    paths: tuple[Path, ...]
    text: str


def extra_guardrail_path(name: PromptName) -> Path:
    """에이전트별 가드레일 문서 경로. 파일이 없을 수 있음.

    Args:
        name: 프롬프트 이름.

    Returns:
        Path: 에이전트 패키지 프롬프트면 같은 폴더 ``guardrail.md``. Tool 프롬프트면
            ``tools/<Tool>/<단계>.guardrail.md`` (단계 없는 이름은 ``tools/<Tool>/guardrail.md``).
    """
    prompt = prompt_path(name)
    if prompt.name == "prompt.md":
        return prompt.with_name("guardrail.md")
    tool, _, step = name.value.partition("/")
    return _TOOLS_DIR / tool / (f"{step}.guardrail.md" if step else "guardrail.md")


@lru_cache(maxsize=None)
def get_guardrail(name: PromptName) -> GuardrailSnapshot:
    """공통 가드레일과 에이전트별 가드레일을 읽어 이은 스냅샷. 이름별로 한 번만 읽음.

    Args:
        name: 붙일 에이전트의 프롬프트 이름.

    Returns:
        GuardrailSnapshot: 읽은 경로와 본문.

    Raises:
        FileNotFoundError: 공통 또는 에이전트별 가드레일 문서가 없는 경우. 실패는 캐시하지 않음.
    """
    paths = (COMMON_GUARDRAIL_PATH, extra_guardrail_path(name))
    parts = [normalize_newlines(path.read_text(encoding="utf-8")).strip() for path in paths]
    return GuardrailSnapshot(name=name, paths=paths, text="\n\n".join(parts) + "\n")


def attach_guardrail(prompt: PromptSnapshot) -> PromptSnapshot:
    """시스템 프롬프트 뒤에 그 에이전트의 가드레일을 빈 줄로 이어 붙인 스냅샷.

    Args:
        prompt: 원래 시스템 프롬프트.

    Returns:
        PromptSnapshot: 이름·경로는 그대로, 본문은 프롬프트 + 가드레일, 지문은 합친 본문 기준.

    Raises:
        FileNotFoundError: 공통 또는 에이전트별 가드레일 문서가 없는 경우.
    """
    text = prompt.text.rstrip("\n") + "\n\n" + get_guardrail(prompt.name).text
    return replace(prompt, text=text, sha256=fingerprint(text))


def clear_guardrail_cache() -> None:
    """읽어 둔 가드레일을 비운다. 개발·평가에서 문서를 고친 뒤 다시 읽을 때 사용."""
    get_guardrail.cache_clear()
