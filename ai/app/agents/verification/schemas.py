"""검증 에이전트가 모델에게 받는 구조화 출력 스키마. 최종 VerificationResult는 agent.py가 병합해 만듦.

- 모델이 채우는 필드만 둠. issue_id·question_id·verified_at은 서버가, status·summary는 코드가 만듦
- strict 모드는 모든 필드를 required로 요구해 기본값 없음
- 클래스 docstring은 JSON 스키마 description으로 모델 요청에 들어가므로 두지 않음
"""

from typing import Literal

from ...schemas.base import StrictModel
from ...schemas.schemas import ToolName, VerificationIssueType as IssueType


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
    issues: list[_Issue]
    additional_tools_required: list[ToolName]
    follow_up_questions: list[_Question]
    checked_finding_ids: list[str]
