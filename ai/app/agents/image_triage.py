"""상품 페이지 후보 이미지를 한 번에 분류하는 에이전트.

작은 크기(썸네일) 이미지 주소를 받아 이미지마다 사양·인증·포장·제품·연출·무관 중 하나로 고름.
몇 장을 남길지, 원본 주소로 바꾸는 일은 쓰는 쪽(URL 입력 조립)이 맡음.
"""

from typing import Any

from ..prompts import PromptName
from ..schemas.agent import ImageTriageResponse
from .base import AgentError, BaseAgent, MissingParsedOutput, ModelFailurePhase

# 한 번에 보내는 이미지 상한. 넘으면 호출부가 나눠 보냄
MAX_IMAGES = 50


class ImageTriageFailedError(AgentError):
    """이미지 분류 모델 호출·파싱 실패, 또는 입력에 없는 이미지 번호를 돌려준 경우."""


class ImageTriageAgent(BaseAgent[ImageTriageResponse]):
    """후보 이미지를 썸네일로 한 번에 분류한다.

    생성자는 BaseAgent 그대로. 모델 미주입 시 AGENT_PROFILES["image_triage"] 프로필로 생성.
    """

    component_name = "image_triage"
    prompt_name = PromptName.IMAGE_TRIAGE
    output_schema = ImageTriageResponse
    error_class = ImageTriageFailedError

    def classify(self, image_urls: list[str], *, subject_id: str) -> ImageTriageResponse:
        """이미지마다 분류를 돌려준다. 번호는 입력 순서 (1부터).

        Args:
            image_urls: 분류할 이미지 주소. 작은 크기일수록 입력 토큰이 적음.
            subject_id: 사용량 기록 대상 ID (상품 페이지 주소 등).

        Returns:
            ImageTriageResponse: 번호순으로 정렬한 분류. 모델이 빠뜨린 번호는 결과에도 없음
                (쓰는 쪽이 분류 없음으로 다룸). 이미지가 없으면 호출 없이 빈 결과.

        Raises:
            ValueError: 이미지가 MAX_IMAGES장을 넘는 경우.
            ImageTriageFailedError: 모델 호출·파싱 실패, 또는 입력에 없는 번호를 돌려준 경우.
        """
        if not image_urls:
            return ImageTriageResponse(items=[])
        if len(image_urls) > MAX_IMAGES:
            raise ValueError(f"이미지는 한 번에 {MAX_IMAGES}장까지 분류합니다: {len(image_urls)}장")

        response = self._invoke(self._messages(_numbered_images(image_urls)), subject_id=subject_id)

        unknown = [item.index for item in response.items if item.index > len(image_urls)]
        if unknown:
            raise ImageTriageFailedError(f"입력에 없는 이미지 번호를 분류했습니다: {unknown} (이미지 {len(image_urls)}장)")
        return ImageTriageResponse(items=sorted(response.items, key=lambda item: item.index))

    def _failure_message(self, phase: ModelFailurePhase, cause: Exception) -> str:
        """호출·파싱 실패 문구.

        Args:
            phase: 실패 단계.
            cause: 원인 예외.

        Returns:
            str: 예외 메시지.
        """
        if phase is ModelFailurePhase.CALL:
            return f"이미지 분류에 실패했습니다: {cause}"
        detail = None if isinstance(cause, MissingParsedOutput) else cause
        return f"모델 응답이 ImageTriageResponse 스키마와 맞지 않습니다: {detail}"


def _numbered_images(image_urls: list[str]) -> list[dict[str, Any]]:
    """이미지마다 앞에 [번호] 글을 붙인 사용자 메시지 블록. 번호와 이미지가 어긋나지 않게 함."""
    blocks: list[dict[str, Any]] = [{"type": "text", "text": f"이미지 {len(image_urls)}장"}]
    for index, url in enumerate(image_urls, 1):
        blocks.append({"type": "text", "text": f"[{index}]"})
        blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks
