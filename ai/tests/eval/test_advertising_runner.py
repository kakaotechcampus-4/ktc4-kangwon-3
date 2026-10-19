"""표시·광고 평가 러너가 모델을 부르기 전 단계(측정 조건·저장)까지 실제로 도는지 확인한다."""

import json
import sys

import pytest

from app.eval import advertising_runner

_REQUIRED_ENV = {
    "OPENAI_API_KEY": "test-key",
    "OPENAI_BASE_URL": "https://example.invalid/v1",
    "OPENAI_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "DATA_GO_KR_KEY": "test",
    "KEY_SAFETYKOREA": "test",
    "LAW_GO_KR_OC": "test",
    "INTERNAL_API_TOKEN": "t" * 40,
    "BE_BASE_URL": "http://localhost:8080",
}


@pytest.fixture
def settings_env(monkeypatch):
    for name, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("MODEL_PROFILE_OVERRIDES", raising=False)


def test_실행하면_표시광고_Tool_프로필을_측정_조건으로_남긴다(settings_env, monkeypatch, tmp_path):
    # 입력 파일(저장소에 없음)과 모델 호출을 빼고 main을 그대로 돌림
    truth = {"cases": [{"product_id": "p1"}], "inputs_sha256_12": "abc"}
    monkeypatch.setattr(advertising_runner, "load_eval_set", lambda path, root: (truth, {"p1": ["방수 원단"]}))
    monkeypatch.setattr(advertising_runner, "run_case", lambda tool, product_id, lines, runs: [])
    monkeypatch.setattr(advertising_runner, "report", lambda truth, results: None)
    out = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["advertising_runner", "--runs", "1", "--out", str(out)])

    assert advertising_runner.main() == 0

    meta = json.loads(out.read_text(encoding="utf-8"))["meta"]
    assert (meta["model"], meta["model_profile"]["profile"]) == ("openai/gpt-4.1-mini", "mini")
    assert meta["prompt_path"] == "app/prompts/advertising.md"


def test_추론_강도를_준_카탈로그_모델은_temperature_없이_프로필을_만든다():
    profile = advertising_runner.model_profile("openai/gpt-6-luna#low")

    assert (profile.model.id, profile.reasoning_effort, profile.temperature) == ("openai/gpt-6-luna", "low", None)


@pytest.mark.parametrize("spec", [
    "openai/gpt-unknown",   # 카탈로그 밖 모델
    "openai/gpt-6-luna",    # 추론 모델에 temperature=0 (추론 강도 없음)
])
def test_카탈로그_밖_모델이나_받지_않는_옵션이면_호출_전에_멈춘다(spec):
    with pytest.raises(SystemExit):
        advertising_runner.model_profile(spec)
