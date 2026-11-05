"""시나리오 평가 러너의 입력 준비·재시도·저장·재채점을 LLM 없이 검증한다."""

import json
import sys
from types import SimpleNamespace

import pytest

from app.agents.extraction import ExtractionFailedError
from app.agents.selection import SelectionFailedError
from app.eval import scenario_runner
from app.eval.errors import RawFixtureMissing
from app.eval.scenario_runner import ProductInput, plan_products, run_product
from app.schemas.schemas import ToolName

TOOLS = [tool.value for tool in ToolName]


def _truth(fixture: str, selected: set[str]) -> dict:
    return {"fixture": fixture, "tools": {t: {"selected": t in selected, "evidence": "e", "why_not_other": "w"} for t in TOOLS}}


def _write_truth(truth_dir, name: str, fixture: str, selected=frozenset({"customs_requirements"})):
    truth_dir.mkdir(parents=True, exist_ok=True)
    (truth_dir / f"{name}.json").write_text(json.dumps(_truth(fixture, set(selected)), ensure_ascii=False), encoding="utf-8")


def _write_raw(raw_dir, folder: str, *files: str):
    (raw_dir / folder).mkdir(parents=True, exist_ok=True)
    for f in files:
        (raw_dir / folder / f).write_text(f"{folder} {f}", encoding="utf-8")


class _FakeProduct:
    def __init__(self, data: dict):
        self._data = data

    def model_dump(self, mode="json"):
        return dict(self._data)


class _FakeExtractor:
    def __init__(self, fail_times: int = 0):
        self.calls = 0
        self.fail_times = fail_times

    def run(self, source):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ExtractionFailedError("가짜 실패")
        return _FakeProduct({"product_name": source.text_blocks[0], "category": None})


class _FakeSelector:
    def __init__(self, selected=frozenset({"customs_requirements"}), fail_times: int = 0):
        self.selected = set(selected)
        self.calls = 0
        self.fail_times = fail_times

    def run(self, product):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise SelectionFailedError("가짜 실패")
        return SimpleNamespace(model_dump=lambda mode="json": {
            "decisions": [{"tool_name": t, "selected": t in self.selected, "reason": "이유"} for t in TOOLS]
        })


def test_원문_폴더가_없는_상품이_있으면_모델을_만들기_전에_멈춘다(tmp_path):
    truth_dir, raw_dir = tmp_path / "truth", tmp_path / "raw"
    _write_truth(truth_dir, "strat_01", "strat_01/text.txt")
    _write_truth(truth_dir, "strat_02", "strat_02/text.txt")
    _write_raw(raw_dir, "strat_01", "text.txt")

    with pytest.raises(RawFixtureMissing):
        plan_products(truth_dir, raw_dir, "text.txt")


def test_펼치기_전_글이_없으면_펼친_글로_대체하고_그_사실을_남긴다(tmp_path):
    truth_dir, raw_dir = tmp_path / "truth", tmp_path / "raw"
    _write_truth(truth_dir, "strat_01", "strat_01/text.txt")
    _write_truth(truth_dir, "strat_02", "strat_02/text.txt")
    _write_raw(raw_dir, "strat_01", "text.txt", "text_as_pasted.txt")
    _write_raw(raw_dir, "strat_02", "text.txt")

    items = {i.name: i for i in plan_products(truth_dir, raw_dir, "text_as_pasted.txt")}

    assert items["strat_01"].text_path.name == "text_as_pasted.txt" and not items["strat_01"].fallback
    assert items["strat_02"].text_path.name == "text.txt" and items["strat_02"].fallback


def test_추출을_회차마다_하고_추출_결과마다_선택한다(tmp_path):
    _write_raw(tmp_path, "p", "text.txt")
    extractor, selector = _FakeExtractor(), _FakeSelector()

    result = run_product(extractor, selector, ProductInput("p", tmp_path / "p" / "text.txt", False), runs=3, retries=2)

    assert (extractor.calls, selector.calls) == (3, 3)
    assert len(result["runs"]) == 3 and all(r["selection"] for r in result["runs"])
    assert result["retries"] == 0 and result["input_fallback"] is False


def test_실패한_회차는_두_번까지_다시_시도하고_그래도_실패하면_빈_회차로_남긴다(tmp_path):
    _write_raw(tmp_path, "p", "text.txt")
    extractor = _FakeExtractor(fail_times=99)

    result = run_product(extractor, _FakeSelector(), ProductInput("p", tmp_path / "p" / "text.txt", False), runs=1, retries=2)

    assert extractor.calls == 3
    assert result["runs"] == [{"extracted": None, "selection": None}]
    assert result["retries"] == 2


def test_선택이_한_번_실패해도_다시_시도해_회차를_채운다(tmp_path):
    _write_raw(tmp_path, "p", "text.txt")
    selector = _FakeSelector(fail_times=1)

    result = run_product(_FakeExtractor(), selector, ProductInput("p", tmp_path / "p" / "text.txt", True), runs=1, retries=2)

    assert result["runs"][0]["selection"] is not None
    assert result["retries"] == 1 and result["input_fallback"] is True


def test_저장한_결과를_재채점하면_같은_숫자가_나온다(tmp_path, monkeypatch, capsys):
    truth_dir, raw_dir = tmp_path / "truth", tmp_path / "raw"
    _write_truth(truth_dir, "strat_01", "strat_01/text.txt", selected={"customs_requirements", "radio_compliance"})
    _write_raw(raw_dir, "strat_01", "text.txt")
    monkeypatch.setattr(scenario_runner, "RESULT_DIR", tmp_path / "out")
    monkeypatch.setattr(scenario_runner, "build_agents", lambda: (_FakeExtractor(), _FakeSelector(), {"model": "가짜"}))
    report = tmp_path / "report.md"

    assert scenario_runner.main(["--truth-dir", str(truth_dir), "--raw-dir", str(raw_dir), "--runs", "2",
                                 "--report", str(report), "--title", "개발"]) == 0
    first = report.read_text(encoding="utf-8")
    saved = next((tmp_path / "out").glob("scenario-*.json"))
    rescored = tmp_path / "again.md"

    assert scenario_runner.main(["--rescore", str(saved), "--report", str(rescored), "--title", "개발"]) == 0

    assert "0/1" in first
    assert rescored.read_text(encoding="utf-8") == first
