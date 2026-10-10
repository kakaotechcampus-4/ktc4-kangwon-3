"""선택 평가 러너의 입력·저장·재채점을 LLM 없이 검증한다."""

import json
import sys
from types import SimpleNamespace

import pytest

from app.eval import selection_runner
from app.eval.runner import prompt_fingerprint, run_metadata
from app.schemas.agent import ToolSelectionItem, ToolSelectionResponse
from app.schemas.schemas import ToolName


def _write_log(path, results, fingerprint="aaa", model="openai/gpt-4.1-mini"):
    meta = {"prompt_sha256": fingerprint, "model": model}
    path.write_text(json.dumps({"meta": meta, "results": results}), encoding="utf-8")
    return path


def test_추출_결과를_픽스처별로_합치고_실패한_회차는_뺀다(tmp_path):
    first = _write_log(tmp_path / "1.json", {"power_bank": [{"category": "a"}, {"_failed": True}]})
    second = _write_log(tmp_path / "2.json", {"power_bank": [{"category": "b"}]})

    outputs, prompt, model = selection_runner.load_extraction_outputs([first, second])

    assert outputs == {"power_bank": [{"category": "a"}, {"category": "b"}]}
    assert (prompt, model) == ("aaa", "openai/gpt-4.1-mini")


def test_추출_프롬프트가_다른_기록은_섞지_않는다(tmp_path):
    first = _write_log(tmp_path / "1.json", {"power_bank": [{}]}, fingerprint="aaa")
    second = _write_log(tmp_path / "2.json", {"power_bank": [{}]}, fingerprint="bbb")

    with pytest.raises(ValueError, match="섞었습니다"):
        selection_runner.load_extraction_outputs([first, second])


def test_프롬프트가_같아도_추출_모델이_다른_기록은_섞지_않는다(tmp_path):
    # 같은 프롬프트로 gpt-4.1-mini와 Luna를 잰 기록(#279)이 섞이면 어떤 추출로 잰 선택인지 알 수 없다
    first = _write_log(tmp_path / "1.json", {"power_bank": [{}]}, model="openai/gpt-4.1-mini")
    second = _write_log(tmp_path / "2.json", {"power_bank": [{}]}, model="openai/gpt-6-luna")

    with pytest.raises(ValueError, match="모델"):
        selection_runner.load_extraction_outputs([first, second])


def test_선택_평가_기록에는_선택_프롬프트_지문이_남는다():
    meta = run_metadata(runs=1, model="openai/gpt-4.1-mini", prompt_path=selection_runner.SELECTION_PROMPT_PATH)

    assert meta["prompt_path"] == "app/prompts/selection.md"
    assert meta["prompt_sha256"] == prompt_fingerprint(selection_runner.SELECTION_PROMPT_PATH)


class _FakeAgent:
    """받은 상품을 기록하고, 무선충전이 false가 아니면 전파를 선택한다."""

    def __init__(self, **kwargs):
        self.seen: list = []

    def select(self, product):
        self.seen.append(product)
        return ToolSelectionResponse(decisions=[
            ToolSelectionItem(
                tool_name=tool,
                selected=tool is ToolName.CUSTOMS or (tool is ToolName.RADIO and product.wireless_charging is not False),
                reason="가짜",
            )
            for tool in ToolName
        ])


def test_같은_추출_결과로_B는_그대로_A는_정답_boolean으로_선택하고_결과를_저장한다(tmp_path, monkeypatch, capsys):
    # power_bank 정답: wireless_charging=null(MagSafe), 전파는 선택해야 한다.
    log = _write_log(tmp_path / "extraction.json", {"power_bank": [{"wireless_charging": False}]})
    agents: list[_FakeAgent] = []
    monkeypatch.setattr(selection_runner, "SelectionAgent", lambda **kw: agents.append(_FakeAgent(**kw)) or agents[-1])
    monkeypatch.setattr(selection_runner, "load_settings", lambda: SimpleNamespace(model="openai/gpt-4.1-mini"))
    monkeypatch.setattr(selection_runner, "RESULT_DIR", tmp_path / "out")
    monkeypatch.setattr(sys, "argv", ["selection_runner", "--extraction-log", str(log), "--fixture", "power_bank"])

    assert selection_runner.main() == 0

    seen = agents[0].seen
    assert [p.wireless_charging for p in seen] == [False, None]  # B 그대로, A는 정답(null)
    saved = json.loads(next((tmp_path / "out").glob("selection-*.json")).read_text(encoding="utf-8"))
    assert saved["meta"]["prompt_path"] == "app/prompts/selection.md"
    assert saved["meta"]["extraction_logs"] == [log.as_posix()]
    assert saved["meta"]["extraction_prompt_sha256"] == "aaa"
    assert saved["meta"]["extraction_model"] == "openai/gpt-4.1-mini"
    radio = lambda r: next(d["selected"] for d in r["decisions"] if d["tool_name"] == "radio_compliance")
    assert radio(saved["results"]["power_bank"]["B"][0]) is False
    assert radio(saved["results"]["power_bank"]["A"][0]) is True
    assert "B에서만 놓침 1회차 radio_compliance → 추출 탓" in capsys.readouterr().out


def test_정답표나_추출_결과가_없으면_모델을_만들기_전에_멈춘다(tmp_path, monkeypatch):
    log = _write_log(tmp_path / "extraction.json", {"power_bank": [{}]})
    monkeypatch.setattr(selection_runner, "SelectionAgent", lambda **kw: pytest.fail("모델을 만들면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["selection_runner", "--extraction-log", str(log), "--fixture", "ali_sample"])

    assert selection_runner.main() == 1


def test_저장된_결과는_재호출_없이_재채점된다(tmp_path, monkeypatch, capsys):
    response = ToolSelectionResponse(decisions=[
        ToolSelectionItem(tool_name=t, selected=t is ToolName.CUSTOMS, reason="r") for t in ToolName
    ]).model_dump(mode="json")
    saved = tmp_path / "selection.json"
    saved.write_text(json.dumps({
        "meta": {"prompt_sha256": "옛지문"},
        "results": {"power_bank": {"products": [{}], "A": [response], "B": [None]}},
    }), encoding="utf-8")
    monkeypatch.setattr(selection_runner, "SelectionAgent", lambda **kw: pytest.fail("모델을 만들면 안 됩니다"))

    assert selection_runner.rescore(saved) == 0

    captured = capsys.readouterr()
    assert "다른 선택 프롬프트" in captured.err
    assert "B: 전 회차 실패" in captured.out
