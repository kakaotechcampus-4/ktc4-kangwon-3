"""코드와 분리한 에이전트별 프롬프트 초안을 읽는다."""

from pathlib import Path


def load_prompt(name: str) -> str:
    if name not in {"extraction", "selection", "verification"}:
        raise ValueError("등록하지 않은 프롬프트입니다.")
    return Path(__file__).with_name(f"{name}.md").read_text(encoding="utf-8")
