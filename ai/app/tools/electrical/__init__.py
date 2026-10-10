"""전기안전 Tool 패키지.

- tool.py: 흐름(조건 추출 → 품목 조회 → 규칙 → 품목 선택 → 결과 조립)
- rules.py: 코드 규칙과 판매 안내 문구
- search.py: 품목표 조회 인터페이스와 구현(법제처 API / DB 스텁)
- evidence.py: 법령 버전 선택, 품목표·공통 비고·별표 13 파서
"""

from .tool import ElectricalTool, ElectricalToolError

__all__ = ["ElectricalTool", "ElectricalToolError"]
