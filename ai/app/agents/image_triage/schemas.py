"""이미지 선별 에이전트 입력. 출력(ImageTriageResponse)은 파이프라인과 같이 쓰는 schemas/agent.py에 있음."""

from pydantic import Field

from ...schemas.base import StrictModel


class ImageTriageInput(StrictModel):
    """분류할 후보 이미지 묶음.

    Attributes:
        image_urls: 분류할 이미지 주소. 작은 크기(썸네일)일수록 입력 토큰이 적음. 번호는 이 순서 (1부터).
        subject_id: 사용량 기록 대상 ID (상품 ID·페이지 주소 등).
    """

    image_urls: list[str] = Field(default_factory=list)
    subject_id: str
