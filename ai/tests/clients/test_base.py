"""외부 통신 공통 도구(키 가리기)를 검증한다."""

from app.clients.base import mask_sensitive_params


def test_mask_sensitive_params는_키_값만_대소문자_구분_없이_가린다():
    text = '근거 "https://x.kr/a?ServiceKey=k1&type=XML&oc=k2" 참고, serviceKey=k3'

    masked = mask_sensitive_params(text)

    assert masked == '근거 "https://x.kr/a?ServiceKey=***&type=XML&oc=***" 참고, serviceKey=k3'
