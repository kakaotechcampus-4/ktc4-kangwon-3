"""CLIP 결정사례 모델의 제약을 DB 없이 검증한다."""

from app.models import HsCase


def test_결정사례는_문서_ID로_중복_적재되지_않는다():
    assert HsCase.__table__.c.doc_id.unique is True


def test_HS_코드는_숫자_10자리_길이로_저장한다():
    # 세관장확인 조회는 숫자 10자리만 받음 (#182)
    assert HsCase.__table__.c.hs_code.type.length == 10
