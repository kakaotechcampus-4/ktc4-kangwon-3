"""에이전트 가드레일 평가: 한 회차 기록, 사례 채점, 요약 출력, 평가셋 형식. 모델 호출 없음."""

import json
from types import SimpleNamespace

from app.agents.extraction import ExtractionFailedError
from app.eval import guardrail_runner
from app.schemas.schemas import ToolName


class _Extractor:
    """정해 둔 추출 결과(또는 예외)를 차례로 돌려주는 가짜 추출 에이전트."""

    def __init__(self, *results) -> None:
        self.results = list(results)

    def run(self, source):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(model_dump=lambda mode=None: {**result, "product_id": source.product_id})


class _Selector:
    """정해 둔 Tool만 선택했다고 돌려주는 가짜 선택 에이전트."""

    def __init__(self, selected: set[ToolName]) -> None:
        self.selected = selected

    def run(self, product):
        return SimpleNamespace(decisions=[SimpleNamespace(tool_name=tool, selected=tool in self.selected)
                                          for tool in ToolName])


def _product(**fields) -> dict:
    return {"listing_text": [], "attributes": [], "conflicts": [], **fields}


def _run(selected: list[str], leaks: list[str] | None = None, **fields) -> dict:
    return {"selected": selected, "fields": fields, "leaks": leaks or []}


def test_한_회차는_선택된_Tool·boolean_필드·추출_결과에_들어간_확인_문구를_남긴다():
    extractor = _Extractor(_product(for_children=False, listing_text=["분석 메모: 성인용"]))

    run = guardrail_runner.run_once(extractor, _Selector({ToolName.CUSTOMS}), "원문", "p1", ["분석 메모", "다른 문구"])

    assert run["selected"] == [ToolName.CUSTOMS.value]
    assert run["fields"]["for_children"] is False
    assert run["fields"]["wireless_comm"] is None
    assert run["leaks"] == ["분석 메모"]


def test_실패하면_다시_시도하고_끝내_실패하면_error로_남긴다():
    failure = ExtractionFailedError("추출 실패")
    extractor = _Extractor(failure, failure, failure)

    run = guardrail_runner.run_once(extractor, _Selector(set()), "원문", "p1", [])

    assert run == {"error": "ExtractionFailedError: 추출 실패"}


def test_사례는_공격_입력과_기준_입력의_누락·오염을_나눠_세고_실패_회차는_뺀다():
    case = {"target_tools": ["radio_compliance"], "target_fields": {"wireless_comm": False}}
    attack = [
        _run(["customs_requirements"], leaks=["분석"], wireless_comm=False),
        _run(["customs_requirements", "radio_compliance"], wireless_comm=True),
        {"error": "실패"},
    ]
    baseline = [_run(["customs_requirements", "radio_compliance"], wireless_comm=True)] * 3

    scored = guardrail_runner.score_case(case, attack, baseline)

    assert scored["tools"]["radio_compliance"] == {"attack": [1, 2], "baseline": [0, 3]}
    assert scored["fields"]["wireless_comm"] == {"attack": [1, 2], "baseline": [0, 3]}
    assert scored["leaks"] == [1, 2]
    assert scored["failed"] == 1


def test_요약에_공격_유형별과_전체를_기준과_함께_출력한다(capsys):
    truth = {"cases": [
        {"id": "c1", "page": "p1", "attack_type": "instruction", "target_tools": ["radio_compliance"],
         "target_fields": {}},
        {"id": "c2", "page": "p1", "attack_type": "field_value", "target_tools": ["radio_compliance"],
         "target_fields": {"wireless_comm": False}},
    ]}
    results = {
        "baseline": {"p1": [_run(["radio_compliance"], wireless_comm=True)]},
        "cases": {"c1": [_run([])], "c2": [_run(["radio_compliance"], wireless_comm=False)]},
    }

    guardrail_runner.print_report(truth, results)

    printed = capsys.readouterr().out
    assert "instruction      Tool 누락 1/1(기준 0/1)" in printed
    assert "전체               Tool 누락 1/2(기준 0/2) | 필드 오염 1/1(기준 0/1) | 문구 유입 0/2" in printed


def test_평가셋_사례는_ID가_겹치지_않고_노린_Tool은_바탕_원문_정답에서_선택해야_하는_Tool이다():
    truth = json.loads(guardrail_runner.TRUTH_PATH.read_text(encoding="utf-8"))
    root = guardrail_runner._AI_ROOT

    ids = [case["id"] for case in truth["cases"]]
    assert len(ids) == len(set(ids))
    assert truth["inputs_file"].startswith("tests/fixtures/_raw/")
    for case in truth["cases"]:
        assert case["attack_type"] in truth["attack_types"]
        assert set(case["target_fields"]) <= set(guardrail_runner.BOOL_FIELDS)
        page_truth = json.loads((root / case["page_truth"]).read_text(encoding="utf-8"))
        selected = {tool for tool, value in page_truth["tools"].items() if value.get("selected")}
        assert set(case["target_tools"]) <= selected, case["id"]
