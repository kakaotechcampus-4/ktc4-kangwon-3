"""추출 프롬프트의 예시가 측정 픽스처의 상품과 겹치지 않는지 확인한다.

측정 픽스처의 상품을 예시로 적으면 그 픽스처의 점수가 부풀려진다(#180). 예시를 바꾸자
기존 3건의 C1이 11.5~13.1%에서 16.4~19.7%로 올랐다. 예시를 고칠 때 측정 픽스처의
상품을 다시 넣지 않도록 막는다.

필드 정의에 가까운 표현("RFID 차단", 제목의 "무선", "보조배터리 등")은 픽스처와 겹쳐도
남겨 두었다(EXTRACTION_EVAL.md 0절). 여기서는 상품 종류로 추론하는 예시만 본다.
"""

import pytest

from app.agents.extraction import PROMPT_PATH

PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

# 지운 예시 표현 -> 겹치던 측정 픽스처
OVERLAPPING_EXAMPLES = {
    "드라이어": "ali_sample",
    "지갑": "wireless_shield_rfid",
    "보조배터리니까": "power_bank",
    "1460mAh": "power_bank",
    "배터리 미포함": "power_bank",
}


@pytest.mark.parametrize("phrase", sorted(OVERLAPPING_EXAMPLES))
def test_측정_픽스처의_상품을_예시로_쓰지_않는다(phrase):
    assert phrase not in PROMPT, f"'{phrase}'는 {OVERLAPPING_EXAMPLES[phrase]} 픽스처와 겹칩니다."
