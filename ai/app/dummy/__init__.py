"""BE·FE 연동 확인용 시나리오 더미 진단 (/dummy/diagnose). 실제 파이프라인 연결([콜백 5/5]) 후 제거.

    - cases: 상품 케이스별 질문·결과
    - scenario: 케이스 선택, 입력에 남기는 표시
    - job: 케이스대로 질문·실패·완료를 돌려주는 진단 함수
"""

from .cases import CASES, DummyCaseName
from .job import run_scenario_diagnosis
from .scenario import mark_case, random_case, read_case

__all__ = ["CASES", "DummyCaseName", "mark_case", "random_case", "read_case", "run_scenario_diagnosis"]
