"""검증 에이전트가 모델에게 받는 구조화 출력 스키마.

issue_id·question_id·verified_at 등 서버가 만드는 값은 없음. 최종 VerificationResult는 agent.py가 병합해 만듦.
"""

from typing import Literal

from ...schemas.base import StrictModel
from ...schemas.schemas import ToolName, VerificationIssueType as IssueType


# 모델이 채우는 필드만 담는다. issue_id·question_id·verified_at은 서버가 만든다.
# Structured Outputs의 strict 모드는 모든 필드를 required로 요구하므로 기본값을 두지 않는다.
class _Issue(StrictModel):
    severity: Literal["critical", "warning", "info"]
    issue_type: IssueType
    description: str
    related_finding_ids: list[str]
    recommended_action: str | None


class _Question(StrictModel):
    question: str
    reason: str
    related_tools: list[ToolName]
    required: bool


class _Review(StrictModel):
    # 최종 status와 summary는 규칙 결과와 병합한 뒤 코드가 계산하므로 모델에게 생성시키지 않는다.
    issues: list[_Issue]
    additional_tools_required: list[ToolName]
    follow_up_questions: list[_Question]
    checked_finding_ids: list[str]
