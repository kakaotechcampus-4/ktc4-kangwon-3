"""코드와 분리한 에이전트별 프롬프트 초안을 읽는다."""

import hashlib
from functools import lru_cache
from pathlib import Path


def prompt_path(name: str) -> Path:
    """등록된 프롬프트 파일 경로. 프롬프트 경로는 이 함수 한 곳에서만 정한다.

    Args:
        name: 프롬프트 이름 (extraction, selection, verification).

    Returns:
        Path: 프롬프트 파일 경로.

    Raises:
        ValueError: 등록하지 않은 이름인 경우.
    """
    if name not in {"extraction", "selection", "verification"}:
        raise ValueError("등록하지 않은 프롬프트입니다.")
    return Path(__file__).with_name(f"{name}.md")


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """등록된 프롬프트를 읽는다. 같은 이름은 프로세스에서 한 번만 읽는다.

    Args:
        name: 프롬프트 이름 (extraction, selection, verification).

    Returns:
        str: 프롬프트 원문.

    Raises:
        ValueError: 등록하지 않은 이름인 경우.
        FileNotFoundError: 프롬프트 파일이 없는 경우.
    """
    return prompt_path(name).read_text(encoding="utf-8")


def prompt_fingerprint(name: str) -> str:
    """모델에 보내는 프롬프트(캐시된 원문)의 지문을 계산한다.

    Args:
        name: 프롬프트 이름.

    Returns:
        str: 줄바꿈을 LF로 맞춘 SHA-256 hex 문자열.

    Raises:
        ValueError: 등록하지 않은 이름인 경우.
        FileNotFoundError: 프롬프트 파일이 없는 경우.
    """
    return fingerprint_text(load_prompt(name))


def fingerprint_text(text: str) -> str:
    """프롬프트 텍스트의 SHA-256 지문을 계산한다.

    CRLF(윈도우)와 LF(CI·서버)에서 같은 값이 나오도록 줄바꿈을 LF로 맞춘다.

    Args:
        text: 프롬프트 텍스트.

    Returns:
        str: SHA-256 hex 문자열.
    """
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()
