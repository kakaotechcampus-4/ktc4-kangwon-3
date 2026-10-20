"""상품 페이지 후보 이미지를 한 번에 분류하는 에이전트.

썸네일 주소를 받아 이미지마다 사양·인증·포장·제품·연출·무관 중 하나로 고름.
몇 장을 남길지, 원본 주소로 바꾸는 일은 쓰는 쪽(URL 입력 조립)이 맡음.
"""

from typing import Any

from ...prompts import PromptName
from ...schemas.agent import ImageTriageResponse
from ..base import AgentError, BaseAgent
from .schemas import ImageTriageInput

MAX_IMAGES = 50


class ImageTriageFailedError(AgentError):
    """이미지 분류 모델 호출·파싱 실패, 또는 입력에 없는 이미지 번호를 돌려준 경우."""


class ImageTriageAgent(BaseAgent[ImageTriageInput, ImageTriageResponse, ImageTriageResponse]):
    """후보 이미지를 썸네일로 한 번에 분류한다. 결과는 번호순, 모델이 빠뜨린 번호는 결과에도 없음."""

    component_name = "image_triage"
    prompt_name = PromptName.IMAGE_TRIAGE
    output_schema = ImageTriageResponse
    error_class = ImageTriageFailedError
    task_name = "이미지 분류"

    def _subject_id(self, input: ImageTriageInput) -> str:
        """사용량 기록 대상 ID.

        Args:
            input: 후보 이미지 묶음.

        Returns:
            str: 기록 대상 ID.
        """
        return input.subject_id

    def _skip(self, input: ImageTriageInput) -> ImageTriageResponse | None:
        """이미지가 없으면 모델 없이 빈 결과.

        Args:
            input: 후보 이미지 묶음.

        Returns:
            ImageTriageResponse | None: 이미지가 없으면 빈 결과, 있으면 None.
        """
        return ImageTriageResponse(items=[]) if not input.image_urls else None

    def _build_messages(self, input: ImageTriageInput) -> list[Any]:
        """이미지마다 [번호] 글을 앞에 붙인 메시지를 만든다 (번호와 이미지가 어긋나지 않게).

        Args:
            input: 후보 이미지 묶음.

        Returns:
            list[Any]: 모델에 보낼 메시지.

        Raises:
            ValueError: 이미지가 MAX_IMAGES장을 넘는 경우 (호출부가 나눠 보내야 함).
        """
        urls = input.image_urls
        # 한 번에 보낼 수 있는 상한 초과
        if len(urls) > MAX_IMAGES:
            raise ValueError(f"이미지는 한 번에 {MAX_IMAGES}장까지 분류합니다: {len(urls)}장")
        blocks: list[dict[str, Any]] = [{"type": "text", "text": f"이미지 {len(urls)}장"}]
        for index, url in enumerate(urls, 1):
            blocks.append({"type": "text", "text": f"[{index}]"})
            blocks.append({"type": "image_url", "image_url": {"url": url}})
        return self._messages(blocks)

    def _finalize(self, output: ImageTriageResponse, input: ImageTriageInput) -> ImageTriageResponse:
        """입력에 없는 번호를 거르고 번호순으로 정렬한다.

        Args:
            output: 모델 분류 결과.
            input: 후보 이미지 묶음.

        Returns:
            ImageTriageResponse: 번호순 분류.

        Raises:
            ImageTriageFailedError: 입력 장수보다 큰 번호를 분류한 경우.
        """
        unknown = [item.index for item in output.items if item.index > len(input.image_urls)]
        # 모델이 입력에 없는 이미지 번호를 만들어 냄
        if unknown:
            raise ImageTriageFailedError(
                f"입력에 없는 이미지 번호를 분류했습니다: {unknown} (이미지 {len(input.image_urls)}장)"
            )
        return ImageTriageResponse(items=sorted(output.items, key=lambda item: item.index))
