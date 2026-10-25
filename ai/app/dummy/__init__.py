"""BE·FE 연동 확인용 시나리오 더미 진단 (/dummy/diagnose). 실제 파이프라인 연결([콜백 5/5]) 후 제거.

    - scenario: 흐름·결과 시나리오, 입력에 남기는 표시
    - results: 결과 종류별 더미 진단 결과
    - job: 시나리오대로 질문·실패·완료를 돌려주는 진단 함수
"""

from .job import run_scenario_diagnosis
from .scenario import DummyFlow, DummyResult, DummyScenario, mark_scenario, random_scenario, read_scenario

__all__ = [
    "DummyFlow", "DummyResult", "DummyScenario", "mark_scenario", "random_scenario", "read_scenario",
    "run_scenario_diagnosis",
]
