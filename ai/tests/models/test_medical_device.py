"""의료기기 품목 모델의 제약을 DB 없이 검증한다."""

from app.models import MedicalDevice


def test_의료기기는_품목일련번호로_고유하다():
    device_sn = MedicalDevice.__table__.c.device_sn

    assert device_sn.unique is True
    assert device_sn.nullable is False
