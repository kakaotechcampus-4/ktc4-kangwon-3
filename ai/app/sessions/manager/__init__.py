"""진단 세션 관리자. 바깥(라우터·콜백·정리 루프)은 SessionManager만 씀.

    - manager: 접수·조회·정리 창구. 아래 셋을 조립
    - capacity: 대기 + 실행 중 자리 (상한)
    - updater: 상태 변경의 단일 통로 (전이표 → 저장 → 이벤트 알림)
    - runner: 진단 함수 한 번 실행 (진행 알림·결말 → 상태 변경)
    - snapshot: 바깥에서 읽어 가는 현황 (지표 수집용)
"""

from .manager import SessionManager
from .snapshot import SessionSnapshot

__all__ = ["SessionManager", "SessionSnapshot"]
