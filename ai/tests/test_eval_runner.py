"""평가 러너 검증. 실제 LLM 호출 없이 입력 검사 부분만 본다."""

import pytest

from app.eval.runner import RawFixtureMissing, run_fixture


def test_원문_픽스처가_없으면_모델을_만들기_전에_멈춘다():
    # 저장소에는 축약본만 커밋되므로 원문이 없는 환경이 정상이다.
    # 이때 API 키 오류나 FileNotFoundError 대신 받는 쪽을 안내해야 한다.
    with pytest.raises(RawFixtureMissing) as exc_info:
        run_fixture(agent=None, name="존재하지_않는_픽스처.txt", runs=1)

    message = str(exc_info.value)
    assert "축약본" in message
    assert "README" in message
