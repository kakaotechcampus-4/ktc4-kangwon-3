"""시나리오 평가 채점: 상품 단위 무누락, 빠뜨림 원인 분류, 실패 회차·이미지 전용 빠뜨림 처리. LLM을 부르지 않는다."""

from app.eval.scenario_scoring import (
    CAUSE_EXTRACTION_FALSE,
    CAUSE_FAILED,
    CAUSE_NO_JUDGEMENT_FIELD,
    CAUSE_SELECTION_MISSED,
    CAUSE_SELECTION_NULL,
    CAUSE_UNCLASSIFIED,
    classify_miss,
    missed_tools,
    over_selected_tools,
    render_report,
    summarize,
)
from app.schemas.schemas import ToolName

TOOLS = [tool.value for tool in ToolName]


def _truth(selected: set[str], image_only: frozenset[str] = frozenset()) -> dict:
    return {"tools": {
        t: {"selected": t in selected, "evidence": "", "why_not_other": "", **({"image_only": True} if t in image_only else {})}
        for t in TOOLS
    }}


def _response(selected: set[str]) -> dict:
    return {"decisions": [{"tool_name": t, "selected": t in selected, "reason": "이유"} for t in TOOLS]}


def _product(*selections: dict | None, extracted: dict | None = None) -> dict:
    return {
        "runs": [{"extracted": None if s is None else (extracted or {}), "selection": s} for s in selections],
        "retries": 0,
        "input_fallback": False,
    }


def test_빠뜨린_Tool과_과잉_선택한_Tool을_따로_돌려준다():
    truth = _truth({"customs_requirements", "electrical_safety"})
    response = _response({"customs_requirements", "radio_compliance"})

    assert missed_tools(truth, response) == [ToolName.ELECTRICAL]
    assert over_selected_tools(truth, response) == [ToolName.RADIO]


def test_실패한_회차는_정답_Tool을_전부_빠뜨린_것으로_센다():
    truth = _truth({"customs_requirements", "electrical_safety"})

    assert sorted(missed_tools(truth, None)) == [ToolName.CUSTOMS, ToolName.ELECTRICAL]
    assert over_selected_tools(truth, None) == []


def test_한_회차라도_빠뜨리면_그_상품은_무누락이_아니다():
    truths = {"p": _truth({"customs_requirements", "radio_compliance"})}
    product = _product(_response({"customs_requirements", "radio_compliance"}), _response({"customs_requirements"}))

    s = summarize({"p": product}, truths, {"p": None})

    assert s["pass_all_runs"] == 0
    assert s["pass_rate_per_run"] == 0.5


def test_모든_회차에서_빠뜨림이_없으면_무누락이다():
    truths = {"p": _truth({"customs_requirements"}), "q": _truth({"customs_requirements"})}
    ok = _response({"customs_requirements", "radio_compliance"})
    products = {"p": _product(ok, ok, ok), "q": _product(ok, _response(set()), ok)}

    s = summarize(products, truths, {"p": None, "q": None})

    assert (s["products"], s["pass_all_runs"], s["pass_rate_all_runs"]) == (2, 1, 0.5)
    assert s["c3_by_tool"]["radio_compliance"] == 5


def test_실패한_회차가_있으면_무누락이_아니고_실패_수가_남는다():
    truths = {"p": _truth({"customs_requirements"})}
    ok = _response({"customs_requirements"})

    s = summarize({"p": _product(ok, None, ok)}, truths, {"p": None})

    assert s["pass_all_runs"] == 0
    assert s["failed_runs"] == 1
    assert s["causes"][CAUSE_FAILED] == 1


def test_추출이_false로_넘겨_놓치면_추출_탓이다():
    ext_truth = {"booleans": {"wireless_comm": {"value": True}}}

    assert classify_miss(ToolName.RADIO, {"wireless_comm": False}, ext_truth) == CAUSE_EXTRACTION_FALSE


def test_정답이_null인_칸을_추출이_false로_넘겨도_추출_탓이다():
    ext_truth = {"booleans": {"wireless_comm": {"value": None}}}

    assert classify_miss(ToolName.RADIO, {"wireless_comm": False}, ext_truth) == CAUSE_EXTRACTION_FALSE


def test_추출이_null로_넘겼는데_놓치면_선택이_null을_없음으로_본_것이다():
    ext_truth = {"booleans": {"wireless_comm": {"value": True}}}

    assert classify_miss(ToolName.RADIO, {"wireless_comm": None}, ext_truth) == CAUSE_SELECTION_NULL


def test_추출이_맞게_넘겼는데_놓치면_선택이_근거를_보고도_놓친_것이다():
    ext_truth = {"booleans": {"wireless_comm": {"value": True}}}

    assert classify_miss(ToolName.RADIO, {"wireless_comm": True}, ext_truth) == CAUSE_SELECTION_MISSED


def test_판단_칸이_없는_Tool의_빠뜨림은_따로_분류한다():
    assert classify_miss(ToolName.CUSTOMS, {}, {"booleans": {}}) == CAUSE_NO_JUDGEMENT_FIELD


def test_추출_정답표가_없으면_원인을_분류하지_않는다():
    assert classify_miss(ToolName.RADIO, {"wireless_comm": False}, None) == CAUSE_UNCLASSIFIED


def test_추출이_실패한_회차의_빠뜨림은_실행_실패로_분류한다():
    assert classify_miss(ToolName.RADIO, None, {"booleans": {}}) == CAUSE_FAILED


def test_이미지에만_근거가_있는_Tool의_빠뜨림은_따로_센다():
    truths = {"p": _truth({"customs_requirements", "radio_compliance"}, image_only=frozenset({"radio_compliance"}))}

    s = summarize({"p": _product(_response({"customs_requirements"}))}, truths, {"p": None})

    assert s["image_only_misses"] == 1
    assert s["c1_by_tool"]["radio_compliance"] == 1


def test_재시도와_입력_대체_수를_모은다():
    truths = {"p": _truth({"customs_requirements"}), "q": _truth({"customs_requirements"})}
    ok = _response({"customs_requirements"})
    p = {**_product(ok), "retries": 2}
    q = {**_product(ok), "input_fallback": True}

    s = summarize({"p": p, "q": q}, truths, {"p": None, "q": None})

    assert (s["retries"], s["input_fallbacks"]) == (2, 1)


def test_빠뜨림_목록에_상품·회차·Tool·원인이_남는다():
    truths = {"p": _truth({"customs_requirements", "radio_compliance"})}
    ext_truth = {"booleans": {"wireless_comm": {"value": True}}}
    product = _product(_response({"customs_requirements"}), extracted={"wireless_comm": False})

    s = summarize({"p": product}, truths, {"p": ext_truth})

    assert s["misses"] == [{"product": "p", "run": 0, "tool": "radio_compliance", "cause": CAUSE_EXTRACTION_FALSE, "image_only": False}]


def test_보고서에_핵심_숫자가_들어간다():
    truths = {"p": _truth({"customs_requirements"})}
    ok = _response({"customs_requirements"})
    s = summarize({"p": _product(ok, ok, ok)}, truths, {"p": None})

    md = render_report(s, {"model": "openai/gpt-4.1-mini"}, "개발 표본 (펼친 글)")

    assert "개발 표본 (펼친 글)" in md
    assert "무누락" in md and "1/1" in md
    assert "openai/gpt-4.1-mini" in md


# 최종 검토 반영 (2026-11-05)
from app.eval.scenario_scoring import CAUSE_NOT_IN_INPUT  # noqa: E402


def test_글_입력에_근거가_없는_Tool의_빠뜨림은_선택_탓으로_찍지_않는다():
    truths = {"p": _truth({"customs_requirements", "electrical_safety"}, image_only=frozenset({"electrical_safety"}))}
    ext_truth = {"booleans": {"electrical_powered": {"value": False}}}
    product = _product(_response({"customs_requirements"}), extracted={"electrical_powered": False})

    s = summarize({"p": product}, truths, {"p": ext_truth})

    assert s["causes"][CAUSE_SELECTION_MISSED] == 0
    assert s["causes"][CAUSE_NOT_IN_INPUT] == 1
    assert s["misses"][0]["image_only"] is True


def test_Tool_하나를_뺀_무누락_상품_수를_낸다():
    truths = {"p": _truth({"customs_requirements", "labeling_advertising_detection"}), "q": _truth({"customs_requirements"})}
    only_customs = _response({"customs_requirements"})
    products = {"p": _product(only_customs, only_customs), "q": _product(only_customs, only_customs)}

    s = summarize(products, truths, {"p": None, "q": None})

    assert s["pass_all_runs"] == 1
    assert s["pass_all_runs_excluding"]["labeling_advertising_detection"] == 2
    assert s["pass_all_runs_excluding"]["customs_requirements"] == 1


def test_보고서에_Tool_하나를_뺀_무누락이_찍힌다():
    truths = {"p": _truth({"customs_requirements", "labeling_advertising_detection"})}
    s = summarize({"p": _product(_response({"customs_requirements"}))}, truths, {"p": None})

    md = render_report(s, {}, "t")

    assert "표시광고 빼고" in md and "1/1" in md
