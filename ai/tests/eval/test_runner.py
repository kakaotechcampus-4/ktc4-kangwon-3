"""평가 러너 검증. 실제 LLM 호출 없이 입력 검사와 기록 부분만 본다."""

import json
import sys
from types import SimpleNamespace

import pytest

from app.eval.runner import (
    EXTRACTION_PROMPT_PATH,
    RawFixtureMissing,
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
    meta = run_metadata(runs=5, model="openai/gpt-4.1-mini")

    assert set(meta) == {
        "run_at", "git_commit", "git_dirty", "model",
        "prompt_path", "prompt_sha256", "runs",
    }
    assert meta["runs"] == 5
    assert meta["model"] == "openai/gpt-4.1-mini"
    assert meta["prompt_path"] == "app/prompts/extraction.md"
    assert meta["prompt_sha256"] == prompt_fingerprint()


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
    meta = run_metadata(runs=1, model="openai/gpt-4.1-mini")

    assert warn_if_prompt_changed(meta) == []


def test_다른_프롬프트로_잰_결과는_경고한다():
    meta = run_metadata(runs=1, model="openai/gpt-4.1-mini")
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
    meta = run_metadata(runs=3, model="openai/gpt-4.1-mini")
    saved = tmp_path / "new.json"
    saved.write_text(json.dumps({"meta": meta, "results": {}}), encoding="utf-8")

    assert rescore(saved) == 0

    printed = capsys.readouterr().err
    assert describe_metadata(meta) in printed


def test_지문을_재는_파일과_에이전트가_읽는_내용이_같다():
    # 경로 상수만 맞춰서는 부족하다. 에이전트가 다른 경로로 읽도록 바뀌면 지문은
    # 엉뚱한 파일에서 나오는데 상수 비교로는 잡히지 않는다. 실제로 읽힌 내용으로 본다.
    from app.agents.extraction import _load_system_prompt

    assert EXTRACTION_PROMPT_PATH.read_text(encoding="utf-8") == _load_system_prompt()


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
    monkeypatch.setattr(runner, "load_settings", lambda: SimpleNamespace(model="openai/gpt-4.1-mini"))
    monkeypatch.setattr(runner, "run_fixture", lambda *a, **k: [{"product_id": "x"}])
    # 채점은 이 테스트의 관심사가 아니다.
    monkeypatch.setattr(runner, "score", lambda *a, **k: None)
    monkeypatch.setattr(runner, "print_report", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["runner", "--fixture", "power_bank", "--runs", "2"])

    assert runner.main() == 0

    saved = json.loads(next((tmp_path / "out").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["meta"]["runs"] == 2
    assert saved["meta"]["model"] == "openai/gpt-4.1-mini"
    assert saved["meta"]["prompt_sha256"] == prompt_fingerprint()
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
    monkeypatch.setattr(runner, "load_settings", lambda: SimpleNamespace(model="openai/gpt-4.1-mini"))
    monkeypatch.setattr(runner, "run_fixture", lambda *a, **k: [{"product_id": "x"}])
    monkeypatch.setattr(runner, "score", lambda *a, **k: None)
    monkeypatch.setattr(runner, "print_report", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["runner", "--fixture", "power_bank", "--runs", "1"])

    assert runner.main() == 0

    assert created == [{"usage_agent": "extraction-eval"}]
