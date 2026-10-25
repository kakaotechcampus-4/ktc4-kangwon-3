"""규제 Tool이 근거로 쓰는 법령·행정규칙 목록. 스케줄러가 이 목록을 미리 받아 두고 점검한다.

각 Tool의 문서 이름·ID 상수를 그대로 가져와 모은다(Tool 코드는 바꾸지 않음).
Tool이 늘거나 근거 문서가 바뀌면 여기에 추가한다.
"""

from dataclasses import dataclass

from ..children import evidence as children
from ..electrical import evidence as electrical


@dataclass(frozen=True)
class LawSource:
    """근거 문서 하나(버전 무관).

    Attributes:
        name: 법제처 검색어로 쓰는 문서 이름.
        document_id: 법령ID(법령) 또는 행정규칙ID(행정규칙). 버전이 바뀌어도 같다.
        is_admrul: 행정규칙(고시·훈령·예규)이면 True.
    """

    name: str
    document_id: str
    is_admrul: bool


LAW_SOURCES: tuple[LawSource, ...] = (
    # 전기 Tool
    LawSource(electrical.RULE_NAME, electrical.RULE_ID, is_admrul=False),
    LawSource(electrical.NOTICE_NAME, electrical.NOTICE_ID, is_admrul=True),
    # 어린이 Tool
    LawSource(children.LAW_NAME, children.LAW_ID, is_admrul=False),
    LawSource(children.RULE_NAME, children.RULE_ID, is_admrul=False),
    LawSource(children.NOTICE_NAME, children.NOTICE_ID, is_admrul=True),
)
