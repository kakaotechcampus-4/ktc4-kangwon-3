"""에이전트 시스템 프롬프트 뒤에 붙이는 가드레일 문서 로더.

공통 문서 ``app/agents/base/guardrail.md``에, 에이전트 프롬프트 옆 추가 문서가 있으면 이어 붙임.
    - 패키지 프롬프트 ``agents/<이름>/prompt.md`` → 같은 폴더 ``guardrail.md``
    - app/prompts 프롬프트 ``prompts/<이름>.md`` → ``prompts/<이름>.guardrail.md``
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ...prompts import PromptName, normalize_newlines, prompt_path

COMMON_GUARDRAIL_PATH = Path(__file__).parent / "guardrail.md"


@dataclass(frozen=True)
class GuardrailSnapshot:
    """한 시점에 읽은 가드레일 본문.

    Attributes:
        name: 붙일 에이전트의 프롬프트 이름.
        paths: 읽은 문서 경로. 공통 문서, 추가 문서(있으면) 순.
        text: 줄바꿈을 LF로 맞추고 문서 사이를 빈 줄로 이은 본문.
    """

    name: PromptName
    paths: tuple[Path, ...]
    text: str


def extra_guardrail_path(name: PromptName) -> Path:
    """에이전트별 추가 가드레일 문서 경로. 파일이 없을 수 있음.

    Args:
        name: 프롬프트 이름.

    Returns:
        Path: 프롬프트가 ``prompt.md``면 같은 폴더 ``guardrail.md``, 아니면 ``<이름>.guardrail.md``.
    """
    prompt = prompt_path(name)
    if prompt.name == "prompt.md":
        return prompt.with_name("guardrail.md")
    return prompt.with_suffix(".guardrail.md")


@lru_cache(maxsize=None)
def get_guardrail(name: PromptName) -> GuardrailSnapshot:
    """공통 가드레일과 에이전트별 추가 가드레일을 읽어 이은 스냅샷. 이름별로 한 번만 읽음.

    Args:
        name: 붙일 에이전트의 프롬프트 이름.

    Returns:
        GuardrailSnapshot: 읽은 경로와 본문.

    Raises:
        FileNotFoundError: 공통 가드레일 문서가 없는 경우. 실패는 캐시하지 않음.
    """
    paths = [COMMON_GUARDRAIL_PATH]
    if (extra := extra_guardrail_path(name)).is_file():
        paths.append(extra)
    parts = [normalize_newlines(path.read_text(encoding="utf-8")).strip() for path in paths]
    return GuardrailSnapshot(name=name, paths=tuple(paths), text="\n\n".join(parts) + "\n")


def clear_guardrail_cache() -> None:
    """읽어 둔 가드레일을 비운다. 개발·평가에서 문서를 고친 뒤 다시 읽을 때 사용."""
    get_guardrail.cache_clear()
