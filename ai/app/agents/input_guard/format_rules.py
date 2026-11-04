"""입력 가드 형식 규칙. 판단 모델 없이 코드로 보는 1단계.

진단 글 입력은 렌더링된 상세페이지를 복사한 자연어(와 URL)뿐이라, 코드·데이터·대화 형식이 나올 일이 거의 없음.
판정 값을 이런 형식으로 미리 써 두는 공격은 판단 모델 점수가 낮게 나와(11-04 실측 0.25~0.64) 형식으로 따로 잡음.
"""

import re

# 규칙 이름 → 정규식
FORMAT_RULES: dict[str, re.Pattern[str]] = {
    "code_block": re.compile(r"^\s*```", re.MULTILINE),
    # 따옴표 키가 있는 객체만. {5V, 1A} 같은 중괄호는 제외
    "json": re.compile(r'\{\s*"[^"\n]+"\s*:'),
    # 문서 구분선, 또는 "키:"로 끝난 줄 다음 줄이 들여쓴 "키:"
    "yaml": re.compile(r"^(---\s*$|[A-Za-z_][\w-]*:\s*\n[ \t]+[A-Za-z_][\w-]*:)", re.MULTILINE),
    # 줄 맨 앞 # + 공백. 복사한 상세페이지 제목에는 #이 붙지 않음
    "markdown_heading": re.compile(r"^#{1,6}\s", re.MULTILINE),
    # 대화 메시지 형식. "System requirements:"처럼 뒤에 단어가 더 붙은 줄은 제외
    # user:는 리뷰 작성자 표시("User: 좋아요")와 겹쳐 제외 (11-04 서버 실측 오탐)
    "role_message": re.compile(r'"role"\s*:|^\s*(system|assistant)\s*:', re.MULTILINE | re.IGNORECASE),
}


def format_hits(text: str) -> list[str]:
    """글에서 걸리는 형식 규칙 이름을 찾는다.

    Args:
        text: 상품 글 또는 재질문 답변.

    Returns:
        list[str]: 걸린 규칙 이름 (FORMAT_RULES 순서). 비면 걸린 규칙 없음.
    """
    return [name for name, pattern in FORMAT_RULES.items() if pattern.search(text)]
