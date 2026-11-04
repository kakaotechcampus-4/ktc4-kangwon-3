"""입력 가드 패키지. 진단 입력(상품 글·이미지, 재질문 답변)에 진단을 조작하려는 지시가 있는지 판단 모델로 본다.

- images.py: 이미지 → 판단 모델용 JPEG data URI (prepare_judge_images)
"""

from .images import JudgeImages, prepare_judge_images

__all__ = ["JudgeImages", "prepare_judge_images"]
