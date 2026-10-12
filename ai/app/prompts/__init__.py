"""에이전트와 평가 러너가 함께 쓰는 프롬프트 로더 (#171 §3).

모델에 넘기는 본문과 기록하는 지문(sha256)은 같은 스냅샷에서 가져옴.
"""

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from hashlib import sha256
from pathlib import Path


class PromptName(StrEnum):
    EXTRACTION = "extraction"
    SELECTION = "selection"
    VERIFICATION = "verification"


@dataclass(frozen=True)
class PromptSnapshot:
    """한 시점에 읽은 프롬프트 본문과 지문.

    Attributes:
        name: 프롬프트 이름.
        path: 프롬프트 파일 경로.
        text: 줄바꿈을 LF로 맞춘 본문. 모델에 이 값을 그대로 넘김.
        sha256: ``text``의 SHA-256 전체 문자열.
    """

    name: PromptName
    path: Path
    text: str
    sha256: str


def normalize_newlines(text: str) -> str:
    """CRLF·CR 줄바꿈을 LF로 맞춘다. 운영체제마다 지문이 달라지지 않게 함."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def fingerprint(text: str) -> str:
    """줄바꿈을 맞춘 본문의 SHA-256. 로더와 평가 러너가 같은 규칙을 씀."""
    return sha256(normalize_newlines(text).encode("utf-8")).hexdigest()


@lru_cache(maxsize=3)
def get_prompt(name: PromptName) -> PromptSnapshot:
    """프롬프트를 읽어 스냅샷으로 돌려준다. 이름별로 한 번만 읽음.

    Args:
        name: 프롬프트 이름.

    Returns:
        PromptSnapshot: 본문과 지문.

    Raises:
        FileNotFoundError: 프롬프트 파일이 없는 경우. 실패는 캐시하지 않음.
    """
    path = Path(__file__).with_name(f"{name.value}.md")
    text = normalize_newlines(path.read_text(encoding="utf-8"))
    return PromptSnapshot(name=name, path=path, text=text, sha256=fingerprint(text))


def clear_prompt_cache() -> None:
    """읽어 둔 프롬프트를 비운다. 개발·평가에서 파일을 고친 뒤 다시 읽을 때 사용."""
    get_prompt.cache_clear()


def load_prompt(name: str) -> str:
    """이름 문자열로 프롬프트 본문을 읽는다. 기존 호출부(health 등) 호환용.

    Args:
        name: 프롬프트 이름 문자열.

    Returns:
        str: 줄바꿈을 LF로 맞춘 본문.

    Raises:
        ValueError: 등록하지 않은 이름인 경우.
        FileNotFoundError: 프롬프트 파일이 없는 경우.
    """
    try:
        prompt_name = PromptName(name)
    except ValueError:
        raise ValueError("등록하지 않은 프롬프트입니다.") from None
    return get_prompt(prompt_name).text
