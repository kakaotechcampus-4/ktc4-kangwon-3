"""별표 원문을 파싱 에이전트 입력으로 다듬기. 표 구조는 그대로 두고 빈칸·선 길이만 줄임.

원문 대조는 다듬기 전 원문으로 함. 다듬어도 테두리 문자·공백을 뺀 글자는 같음.
"""

import re

# 표 테두리 문자 (U+2500–257F)
_BOX_DRAWING = frozenset(chr(code) for code in range(0x2500, 0x2580))
# 가로선 문자. 길이만 의미 없어 한 글자로 줄임
_HORIZONTAL_RUN_RE = re.compile(r"([─━┄┅┈┉╌╍═])\1+")
# 칸을 채운 공백 (전각 공백 포함)
_SPACE_RUN_RE = re.compile(r"[ \t　]+")


def _is_border(line: str) -> bool:
    return all(char in _BOX_DRAWING or char == " " for char in line)


def compact_annex(content: str) -> str:
    """빈 줄을 지우고, 연속 공백을 하나로, 가로선 줄의 선 길이를 한 글자로 줄인다.

    가로선 줄의 교차 문자(┼ ┴ ┬ 등)와 선이 없는 칸 자리(공백)는 남김.
    세로로 합친 칸의 범위를 이 문자로 판단하기 때문.

    Args:
        content: 별표 원문.

    Returns:
        str: 다듬은 원문.
    """
    lines = []
    for line in content.splitlines():
        line = _SPACE_RUN_RE.sub(" ", line).strip()
        if not line:
            continue
        if _is_border(line):
            line = _HORIZONTAL_RUN_RE.sub(r"\1", line)
        lines.append(line)
    return "\n".join(lines)
