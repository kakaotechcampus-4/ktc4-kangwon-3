"""표시·광고 Tool 평가셋 채점. 모델을 부르지 않는 순수 함수만 둔다.

평가셋: tests/eval_truth_advertising/dev.json. 문구 단위로 맞힘·놓침·오탐·미분류를 센다.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import InputsMismatch


def normalize(text: str) -> str:
    """대조용 정규화. Tool의 인용 대조와 같은 규칙(공백·영문 대소문자 무시)이다."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def overlaps(detected: str, labeled: str) -> bool:
    """탐지 문구가 정답 문구를 포함하거나 그 안에 포함되면 같은 문구로 본다."""
    a, b = normalize(detected), normalize(labeled)
    return bool(a) and bool(b) and (a in b or b in a)


@dataclass
class CaseScore:
    """상품 하나, 실행 1회의 채점 결과."""

    hits: list[str] = field(default_factory=list)  # 잡은 must_flag 정답 문구
    misses: list[str] = field(default_factory=list)  # 놓친 must_flag 정답 문구
    false_positives: list[str] = field(default_factory=list)  # must_not_flag에 걸린 탐지 문구
    unlabeled: list[str] = field(default_factory=list)  # 어느 목록에도 없는 탐지 문구. 사람이 정한다
    type_mismatches: list[str] = field(default_factory=list)  # 잡았지만 유형이 다른 정답 문구


def score_case(case: dict, detected: list[dict]) -> CaseScore:
    """탐지 결과를 정답과 대조한다.

    Args:
        case: 평가셋의 케이스(must_flag, must_not_flag, acceptable).
        detected: Tool 결과의 detected_phrases를 dict로 바꾼 목록(text, risk_type).

    Returns:
        CaseScore: 맞힘·놓침·오탐·미분류. 탐지 하나가 정답 여러 개에 걸치면 모두 맞힌 것으로 센다.
    """
    score = CaseScore()
    for item in case["must_flag"]:
        matched = [phrase for phrase in detected if overlaps(phrase["text"], item["text"])]
        if not matched:
            score.misses.append(item["text"])
            continue
        score.hits.append(item["text"])
        if all(phrase["risk_type"] != item["risk_type"] for phrase in matched):
            score.type_mismatches.append(item["text"])

    for phrase in detected:
        text = phrase["text"]
        if any(overlaps(text, item["text"]) for item in case["must_flag"] + case["acceptable"]):
            continue
        if any(overlaps(text, item["text"]) for item in case["must_not_flag"]):
            score.false_positives.append(text)
        else:
            score.unlabeled.append(text)
    return score


def inputs_digest(text: str) -> str:
    """입력 파일 지문. 줄바꿈을 LF로 맞춘 SHA-256 앞 12자(_raw MANIFEST와 같은 규칙)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def load_eval_set(truth_path: Path, ai_root: Path) -> tuple[dict, dict[str, list[str]]]:
    """평가셋과 로컬 입력(listing_text)을 읽고 지문을 대조한다.

    Raises:
        FileNotFoundError: 로컬 입력 파일이 없다(저장소에 없음, 노션 zip으로 받는다).
        InputsMismatch: 입력 파일 지문이 평가셋과 다르다.
    """
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    inputs_text = (ai_root / truth["inputs_file"]).read_text(encoding="utf-8")
    digest = inputs_digest(inputs_text)
    if digest != truth["inputs_sha256_12"]:
        raise InputsMismatch(f"입력 지문 {digest}가 평가셋 {truth['inputs_sha256_12']}와 다릅니다.")
    return truth, json.loads(inputs_text)
