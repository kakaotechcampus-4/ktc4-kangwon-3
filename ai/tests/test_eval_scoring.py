"""정답표와 N회 실행 결과를 대조하는 채점기 검증. LLM을 부르지 않는다."""

import pytest

from app.eval.grading import Grade, Stability
from app.eval.scoring import score


def _run(**overrides) -> dict:
    """Product.model_dump() 모양의 최소 실행 결과."""
    base = {
        "product_id": "t1",
        "source_url": None,
        "product_name": "MagSafe 케이스",
        "target_age": None,
        "battery_included": None,
        "attributes": [],
        "conflicts": [],
    }
    base.update(overrides)
    return base


def test_세_번_모두_정답이면_안정_정답으로_집계된다():
    truth = {"fixture": "t", "booleans": {"battery_included": {"value": None}}}
    report = score(truth, [_run(), _run(), _run()])

    assert report.runs == 3
    counts = report.counts()
    assert counts["stable_ok"] == 1
    assert counts["c1"] == 0


def test_세_번_모두_같은_오답이면_안정_오답으로_잡힌다():
    # 정답은 "모름"인데 매번 false로 확정 -> 고칠 수 있는 체계적 오류.
    truth = {"fixture": "t", "booleans": {"battery_included": {"value": None}}}
    runs = [_run(battery_included=False) for _ in range(3)]

    report = score(truth, runs)

    assert report.counts()["stable_wrong"] == 1
    assert report.counts()["c1"] == 1
    assert report.fields[0].stability is Stability.STABLE_WRONG


def test_런마다_값이_갈리면_불안정과_심각한_진동이_함께_잡힌다():
    truth = {"fixture": "t", "booleans": {"battery_included": {"value": None}}}
    runs = [_run(battery_included=True), _run(battery_included=False), _run(battery_included=True)]

    report = score(truth, runs)

    counts = report.counts()
    assert counts["unstable"] == 1
    assert counts["stable_wrong"] == 0
    # True <-> False 진동은 따로 센다.
    assert counts["hard_flip"] == 1


def test_확정과_null_사이_진동은_심각한_진동으로_세지_않는다():
    truth = {"fixture": "t", "booleans": {"battery_included": {"value": True}}}
    runs = [_run(battery_included=True), _run(battery_included=None), _run(battery_included=None)]

    counts = score(truth, runs).counts()

    assert counts["unstable"] == 1
    assert counts["hard_flip"] == 0


def test_가장_나쁜_등급을_필드_등급으로_삼는다():
    # 3회 중 1회만 치명이어도 그 필드는 치명으로 본다.
    truth = {"fixture": "t", "booleans": {"battery_included": {"value": True}}}
    runs = [_run(battery_included=True), _run(battery_included=False), _run(battery_included=True)]

    report = score(truth, runs)

    assert report.fields[0].worst is Grade.C1


def test_요구한_모순을_놓치면_치명으로_잡힌다():
    truth = {"fixture": "t", "conflicts_required": [{"must_contain": "1460mAh"}]}

    found = score(truth, [_run(conflicts=["배터리 용량 표기(1460mAh)가 있으나 ..."])] * 3)
    missed = score(truth, [_run(conflicts=[])] * 3)

    assert found.counts()["c1"] == 0
    assert missed.counts()["c1"] == 1


def test_요구한_속성과_금지한_속성을_나눠_센다():
    truth = {
        "fixture": "t",
        "attributes_required": [{"name": "배터리 용량", "value": "1460mAh"}],
        "attributes_forbidden": [{"name": "정격전압", "value": "220V"}],
    }
    runs = [_run(attributes=[{"name": "정격전압", "value": "220V"}])] * 3

    counts = score(truth, runs).counts()

    # 요구한 건 놓쳤으니 미탐(C2), 없는 걸 지어냈으니 치명(C1).
    assert counts["c2"] == 1
    assert counts["c1"] == 1


def test_원문_보존_필드를_줄여_쓰면_치명이다():
    truth = {"fixture": "t", "verbatim": {"target_age": {"value": "만 14세 이상"}}}
    runs = [_run(target_age="14세")] * 3

    assert score(truth, runs).counts()["c1"] == 1


def test_정답표에_기준이_없는_필드는_채점하지_않고_따로_센다():
    # 채점 안 한 필드를 정답으로 세면 정확도가 부풀려진다.
    truth = {"fixture": "t", "booleans": {"battery_included": {"value": None}}}

    report = score(truth, [_run()])

    assert report.counts()["graded_fields"] == 1
    assert "product_name" in report.ungraded
    assert "target_age" in report.ungraded
    # 식별자·출처는 모델이 만들지 않으므로 미채점으로도 세지 않는다.
    assert "product_id" not in report.ungraded
    assert "source_url" not in report.ungraded


def test_실행_결과가_없으면_채점할_수_없다():
    with pytest.raises(ValueError):
        score({"fixture": "t"}, [])


def test_빈_문자열을_준_필드는_지어낸_것으로_세지_않는다():
    # 스키마 validator가 ""를 None으로 바꾸지만, 실행 결과 dict를 직접 넘기는
    # 경로(저장된 로그 재채점 등)는 그 validator를 거치지 않는다.
    truth = {"fixture": "t", "verbatim": {"target_age": {"value": None}}}

    counts = score(truth, [_run(target_age=""), _run(target_age="")]).counts()

    assert counts["c1"] == 0
    assert counts["stable_ok"] == 1


def test_listing_text에서_놓친_판매자_문구는_치명으로_잡힌다():
    truth = {"fixture": "t", "listing_text_required": [{"must_contain": "연약한 피부에 적합한"}]}

    found = score(truth, [_run(listing_text=["아이들의 연약한 피부에 적합한 소형 헤어 드라이어"])] * 3)
    missed = score(truth, [_run(listing_text=["소형 헤어 드라이어"])] * 3)

    assert found.listing_counts()["c1_missing"] == 0
    assert missed.listing_counts()["c1_missing"] == 1


def test_listing_text에_섞인_리뷰와_플랫폼_문구는_오탐으로_잡힌다():
    truth = {"fixture": "t", "listing_text_forbidden": [{"must_not_contain": "효과는 100%"}]}

    mixed = score(truth, [_run(listing_text=["RFID 차단 지갑", "하지만 효과는 100%입니다."])] * 3)
    clean = score(truth, [_run(listing_text=["RFID 차단 지갑"])] * 3)

    assert mixed.listing_counts()["c3_mixed"] == 1
    assert clean.listing_counts()["c3_mixed"] == 0


def test_listing_text_채점은_기존_집계의_분모를_바꾸지_않는다():
    # 분모가 늘면 아무것도 안 고쳤는데 C1 비율이 내려가 보이고, v1·v2 측정치와 비교할 수 없다.
    base = {"fixture": "t", "booleans": {"battery_included": {"value": True}}}
    with_listing = {
        **base,
        "listing_text_required": [{"must_contain": "없는 문구"}],
        "listing_text_forbidden": [{"must_not_contain": "섞인 문구"}],
    }
    runs = [_run(battery_included=False, listing_text=["섞인 문구"])] * 3

    assert score(with_listing, runs).counts() == {
        **score(base, runs).counts(),
        # listing_text는 따로 채점했으므로 미채점 목록에서만 빠진다.
        "ungraded_fields": score(base, runs).counts()["ungraded_fields"] - 1,
    }


def test_listing_text_기준이_있으면_미채점으로_세지_않는다():
    truth = {"fixture": "t", "listing_text_forbidden": [{"must_not_contain": "x"}]}
    report = score(truth, [_run(listing_text=[])])

    assert "listing_text" not in report.ungraded
