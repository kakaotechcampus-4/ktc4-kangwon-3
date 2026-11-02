"""실제 진단 파이프라인을 세션 진단 함수로 잇는 곳 ([콜백 5/5] #320).

    - assembly: 기동 때 한 번 만드는 파이프라인 부품
"""

from .assembly import PipelineParts, build_parts, build_tools

__all__ = ["PipelineParts", "build_parts", "build_tools"]
