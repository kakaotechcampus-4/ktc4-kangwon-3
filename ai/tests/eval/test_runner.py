"""평가 러너 검증. 실제 LLM 호출 없이 입력 검사와 기록 부분만 본다."""

import json
import sys
from types import SimpleNamespace

import pytest

import app.agents.base.guardrail as guardrail_module
from app.agents.base.guardrail import clear_guardrail_cache
from app.agents.extraction import ExtractionAgent
from app.config import MODEL_PROFILES
from app.eval.errors import RawFixtureMissing
from app.eval.runner import (
    EXTRACTION_PROMPT_PATH,
    describe_metadata,
    prompt_fingerprint,
    rescore,
    run_fixture,
    run_metadata,
    warn_if_prompt_changed,
)


def test_원문_픽스처가_없으면_모델을_만들기_전에_멈춘다():
    # 저장소에는 축약본만 커밋되므로 원문이 없는 환경이 정상이다.
    # 이때 API 키 오류나 FileNotFoundError 대신 받는 쪽을 안내해야 한다.
    with pytest.raises(RawFixtureMissing) as exc_info:
        run_fixture(agent=None, name="존재하지_않는_픽스처.txt", runs=1)

    message = str(exc_info.value)
    assert "축약본" in message
    assert "README" in message


def test_실행_기록에_프롬프트_지문과_커밋이_남는다():
    # 프롬프트가 바뀌면 이전 수치와 비교하면 안 된다. 그 판단에 필요한 값이 다 있어야 한다.
    meta = run_metadata(runs=5, profile=MODEL_PROFILES["mini"])

    assert set(meta) == {
        "run_at", "git_commit", "git_dirty", "model", "model_profile",
        "prompt_path", "prompt_sha256", "runs",
    }
    assert meta["runs"] == 5
    assert meta["model"] == "openai/gpt-4.1-mini"
    assert meta["model_profile"] == MODEL_PROFILES["mini"].metadata()
    assert meta["prompt_path"] == "app/agents/extraction/prompt.md"
    assert meta["prompt_sha256"] == ExtractionAgent.system_prompt().sha256


def test_기록_지문은_가드레일까지_붙인_시스템_프롬프트_기준이다(tmp_path, monkeypatch):
    # 가드레일만 바꿔도 모델 입력이 달라지므로 프롬프트 파일 지문과 구분돼야 함
    extra = tmp_path / "guardrail.md"
    extra.write_text("에이전트 규칙\n", encoding="utf-8")
    monkeypatch.setattr(guardrail_module, "extra_guardrail_path", lambda name: extra)
    monkeypatch.setattr(ExtractionAgent, "uses_guardrail", True)
    clear_guardrail_cache()

    try:
        meta = run_metadata(runs=1, profile=MODEL_PROFILES["mini"])
        guarded = ExtractionAgent.system_prompt().sha256
    finally:
        clear_guardrail_cache()

    assert meta["prompt_sha256"] == guarded
    assert meta["prompt_sha256"] != prompt_fingerprint(EXTRACTION_PROMPT_PATH)


def test_프롬프트가_한_글자만_달라도_지문이_바뀐다(tmp_path):
    original = tmp_path / "a.md"
    edited = tmp_path / "b.md"
    original.write_text("boolean 필드를 false로 채우지 않는다.", encoding="utf-8")
    edited.write_text("boolean 필드를 false로 채우지 않는다!", encoding="utf-8")

    assert prompt_fingerprint(original) != prompt_fingerprint(edited)


def test_줄바꿈_방식이_달라도_같은_프롬프트로_본다(tmp_path):
    # 윈도우(CRLF)에서 잰 결과와 CI(LF)에서 잰 결과가 서로 다른 프롬프트로 잡히면
    # "바뀌지 않았는데 바뀌었다"는 잘못된 경고가 뜬다.
    lf = tmp_path / "lf.md"
    crlf = tmp_path / "crlf.md"
    lf.write_bytes(b"1. none\n2. false\n")
    crlf.write_bytes(b"1. none\r\n2. false\r\n")

    assert prompt_fingerprint(lf) == prompt_fingerprint(crlf)


def test_지금_프롬프트로_잰_결과는_경고하지_않는다():
    meta = run_metadata(runs=1, profile=MODEL_PROFILES["mini"])

    assert warn_if_prompt_changed(meta) == []


def test_다른_프롬프트로_잰_결과는_경고한다():
    meta = run_metadata(runs=1, profile=MODEL_PROFILES["mini"])
    meta["prompt_sha256"] = "0" * 64

    warnings = warn_if_prompt_changed(meta)

    assert len(warnings) == 1
    assert "다른 프롬프트" in warnings[0]


def test_메타가_없는_예전_결과는_알_수_없다고_알린다():
    warnings = warn_if_prompt_changed(None)

    assert len(warnings) == 1
    assert "알 수 없습니다" in warnings[0]


def test_메타가_없는_예전_형식도_재채점된다(tmp_path, capsys):
    # 이 변경 이전에 저장한 파일에는 meta가 없다. 그래도 재채점은 돌아가야 한다.
    old_format = tmp_path / "old.json"
    old_format.write_text(json.dumps({"runs": 5, "results": {}}), encoding="utf-8")

    assert rescore(old_format) == 0
    assert "알 수 없습니다" in capsys.readouterr().err


def test_재채점은_어떤_조건으로_잰_값인지_먼저_알린다(tmp_path, capsys):
    meta = run_metadata(runs=3, profile=MODEL_PROFILES["mini"])
    saved = tmp_path / "new.json"
    saved.write_text(json.dumps({"meta": meta, "results": {}}), encoding="utf-8")

    assert rescore(saved) == 0

    printed = capsys.readouterr().err
    assert describe_metadata(meta) in printed


def test_지문을_재는_파일과_에이전트가_읽는_내용이_같다():
    # 경로 상수만 맞춰서는 부족하다. 에이전트가 다른 경로로 읽도록 바뀌면 지문은
    # 엉뚱한 파일에서 나오는데 상수 비교로는 잡히지 않는다. 실제로 읽힌 내용으로 본다.
    from app.agents.extraction import ExtractionAgent
    from app.prompts import get_prompt

    agent_prompt = get_prompt(ExtractionAgent.prompt_name)
    assert agent_prompt.path == EXTRACTION_PROMPT_PATH
    assert EXTRACTION_PROMPT_PATH.read_text(encoding="utf-8") == agent_prompt.text


def test_지문이_없는_기록도_알_수_없다고_알린다():
    warnings = warn_if_prompt_changed({"model": "openai/gpt-4.1-mini", "runs": 5})

    assert len(warnings) == 1
    assert "프롬프트 지문이 없습니다" in warnings[0]


def test_요약_한_줄_때문에_재채점이_죽지_않는다():
    # 손으로 편집했거나 형식이 다른 기록도 읽을 수 있어야 한다.
    assert "알 수 없음" in describe_metadata({})


def test_실제로_저장되는_파일에_meta가_들어간다(tmp_path, monkeypatch):
    # 이 PR의 약속 자체. 러너를 끝까지 돌려서 파일을 확인한다(LLM 호출은 대체).
    from app.eval import runner

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    truth = json.loads((runner.TRUTH_DIR / "power_bank.json").read_text(encoding="utf-8"))
    (raw_dir / truth["fixture"]).write_text("본문", encoding="utf-8")

    monkeypatch.setattr(runner, "RAW_DIR", raw_dir)
    monkeypatch.setattr(runner, "RESULT_DIR", tmp_path / "out")
    monkeypatch.setattr(runner, "ExtractionAgent", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(runner, "agent_profile", lambda name: MODEL_PROFILES["mini"])
    monkeypatch.setattr(runner, "run_fixture", lambda *a, **k: [{"product_id": "x"}])
    # 채점은 이 테스트의 관심사가 아니다.
    monkeypatch.setattr(runner, "score", lambda *a, **k: None)
    monkeypatch.setattr(runner, "print_report", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["runner", "--fixture", "power_bank", "--runs", "2"])

    assert runner.main() == 0

    saved = json.loads(next((tmp_path / "out").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["meta"]["runs"] == 2
    assert saved["meta"]["model"] == "openai/gpt-4.1-mini"
    assert saved["meta"]["prompt_sha256"] == ExtractionAgent.system_prompt().sha256
    assert saved["results"] == {"power_bank": [{"product_id": "x"}]}


def test_평가_러너는_평가용_이름으로_에이전트를_만든다(tmp_path, monkeypatch):
    # 평가로 쓴 비용이 운영 비용과 같은 이름으로 쌓이면 나눠 볼 수 없다.
    from app.eval import runner

    created: list[dict] = []
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    truth = json.loads((runner.TRUTH_DIR / "power_bank.json").read_text(encoding="utf-8"))
    (raw_dir / truth["fixture"]).write_text("본문", encoding="utf-8")

    monkeypatch.setattr(runner, "RAW_DIR", raw_dir)
    monkeypatch.setattr(runner, "RESULT_DIR", tmp_path / "out")
    monkeypatch.setattr(runner, "ExtractionAgent",
                        lambda **kwargs: created.append(kwargs) or SimpleNamespace(**kwargs))
    monkeypatch.setattr(runner, "agent_profile", lambda name: MODEL_PROFILES["mini"])
    monkeypatch.setattr(runner, "run_fixture", lambda *a, **k: [{"product_id": "x"}])
    monkeypatch.setattr(runner, "score", lambda *a, **k: None)
    monkeypatch.setattr(runner, "print_report", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["runner", "--fixture", "power_bank", "--runs", "1"])

    assert runner.main() == 0

    assert created == [{"usage_agent": "extraction-eval"}]


def test_요약_한_줄에_프로필과_추론_강도를_보인다():
    meta = run_metadata(runs=1, profile=MODEL_PROFILES["luna-low"])

    assert "모델 openai/gpt-6-luna (luna-low, 추론 low)" in describe_metadata(meta)
    # 프로필이 없는 예전 기록은 모델 이름만
    assert "모델 openai/gpt-4.1-mini / " in describe_metadata({"model": "openai/gpt-4.1-mini"})


def _truth_like_power_bank(fixture: str) -> dict:
    from app.eval import runner

    truth = json.loads((runner.TRUTH_DIR / "power_bank.json").read_text(encoding="utf-8"))
    truth["fixture"] = fixture
    return truth


def _patch_runner_without_llm(runner, monkeypatch, tmp_path, argv: list[str]) -> None:
    monkeypatch.setattr(runner, "RESULT_DIR", tmp_path / "out")
    monkeypatch.setattr(runner, "ExtractionAgent", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(runner, "agent_profile", lambda name: MODEL_PROFILES["mini"])
    monkeypatch.setattr(runner, "run_fixture", lambda *a, **k: [{"product_id": "x"}])
    monkeypatch.setattr(runner, "score", lambda *a, **k: None)
    monkeypatch.setattr(runner, "print_report", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["runner", *argv])


def test_정답표_폴더를_바꿔_확정_전_초안으로도_잰다(tmp_path, monkeypatch):
    # 수집한 표본의 정답표 초안은 확정 전까지 _raw/truth_drafts에 둔다(#567).
    # 초안으로 먼저 재서 모델과 어긋난 칸만 검토하려면 러너가 다른 폴더의 정답표를 읽어야 한다.
    from app.eval import runner

    raw_dir = tmp_path / "raw"
    (raw_dir / "strat_01").mkdir(parents=True)
    (raw_dir / "strat_01" / "text.txt").write_text("본문", encoding="utf-8")
    truth_dir = tmp_path / "drafts"
    truth_dir.mkdir()
    (truth_dir / "strat_01_wallet.json").write_text(
        json.dumps(_truth_like_power_bank("strat_01/text.txt"), ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "RAW_DIR", raw_dir)
    _patch_runner_without_llm(runner, monkeypatch, tmp_path, ["--all", "--runs", "1", "--truth-dir", str(truth_dir)])

    assert runner.main() == 0

    saved = json.loads(next((tmp_path / "out").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["results"] == {"strat_01_wallet": [{"product_id": "x"}]}
    # 재채점 때 같은 정답표를 찾을 수 있어야 한다.
    assert saved["truth_dir"] == str(truth_dir)


def test_재채점은_기록된_정답표_폴더를_쓴다(tmp_path, capsys):
    from app.eval import runner

    truth_dir = tmp_path / "drafts"
    truth_dir.mkdir()
    (truth_dir / "strat_01_wallet.json").write_text(
        json.dumps(_truth_like_power_bank("strat_01/text.txt"), ensure_ascii=False), encoding="utf-8"
    )
    saved = tmp_path / "result.json"
    saved.write_text(json.dumps({
        "meta": None, "truth_dir": str(truth_dir),
        "results": {"strat_01_wallet": [{"product_id": "x", "attributes": []}]},
    }), encoding="utf-8")

    assert rescore(saved) == 0

    assert "strat_01/text.txt" in capsys.readouterr().out


def test_원문_폴더를_옵션으로_바꿔_저장소_밖의_원문으로_잰다(tmp_path, monkeypatch):
    # 임시 워크트리에서 평가할 때 _raw로 가는 정션을 만들지 않고 원문 폴더를 직접 가리킨다(11/5 사고 재발 방지).
    from app.eval import runner

    raw_dir = tmp_path / "elsewhere"
    (raw_dir / "strat_01").mkdir(parents=True)
    (raw_dir / "strat_01" / "text.txt").write_text("본문", encoding="utf-8")
    truth_dir = tmp_path / "drafts"
    truth_dir.mkdir()
    (truth_dir / "strat_01_wallet.json").write_text(
        json.dumps(_truth_like_power_bank("strat_01/text.txt"), ensure_ascii=False), encoding="utf-8"
    )
    seen = {}
    _patch_runner_without_llm(runner, monkeypatch, tmp_path,
                              ["--all", "--runs", "1", "--truth-dir", str(truth_dir), "--raw-dir", str(raw_dir)])
    monkeypatch.setattr(runner, "run_fixture",
                        lambda agent, name, runs, raw_dir=None: seen.update(raw_dir=raw_dir) or [{"product_id": "x"}])

    assert runner.main() == 0

    assert seen["raw_dir"] == raw_dir


def test_run_fixture는_받은_원문_폴더에서_읽는다(tmp_path):
    from app.eval.runner import run_fixture

    raw_dir = tmp_path / "elsewhere"
    raw_dir.mkdir()
    (raw_dir / "a.txt").write_text("원문", encoding="utf-8")
    agent = SimpleNamespace(run=lambda source: SimpleNamespace(model_dump=lambda mode: {"text": source.text_blocks[0]}))

    assert run_fixture(agent, "a.txt", 1, raw_dir=raw_dir) == [{"text": "원문"}]
