"""근거 문서 목록이 Tool 상수와 맞고 겹치지 않는지 검증한다."""

from app.tools.children import evidence as children
from app.tools.common.law_sources import LAW_SOURCES, LawSource
from app.tools.customs import evidence as customs
from app.tools.electrical import evidence as electrical
from app.tools.food_drug import evidence as food_drug
from app.tools.radio import evidence as radio


def test_문서는_종류와_ID로_한_번씩만_들어간다():
    keys = [(source.is_admrul, source.document_id) for source in LAW_SOURCES]

    assert len(keys) == len(set(keys))


def test_Tool이_불러오는_문서가_모두_들어_있다():
    expected = {
        LawSource(electrical.RULE_NAME, electrical.RULE_ID, False),
        LawSource(electrical.NOTICE_NAME, electrical.NOTICE_ID, True),
        LawSource(children.LAW_NAME, children.LAW_ID, False),
        LawSource(children.RULE_NAME, children.RULE_ID, False),
        LawSource(children.NOTICE_NAME, children.NOTICE_ID, True),
        LawSource(radio.LAW_NAME, radio.LAW_ID, False),
        LawSource(radio.DECREE_NAME, radio.DECREE_ID, False),
        LawSource(radio.NOTICE_NAME, radio.NOTICE_ID, True),
        LawSource(customs.ACT_NAME, customs.ACT_ID, False),
        LawSource(customs.DECREE_NAME, customs.DECREE_ID, False),
        LawSource(customs.NOTICE_NAME, customs.NOTICE_ID, True),
        *(LawSource(*doc, False) for doc in (
            food_drug.FOOD_ACT, food_drug.IMPORTED_FOOD_ACT, food_drug.IMPORTED_FOOD_DECREE, food_drug.DEVICE_ACT,
            food_drug.DEVICE_RULE, food_drug.HEALTH_FOOD_ACT, food_drug.COSMETICS_ACT, food_drug.COSMETICS_RULE)),
        LawSource(*food_drug.DEVICE_NOTICE, True),
        LawSource(*food_drug.COSMETICS_NOTICE, True),
    }

    assert expected <= set(LAW_SOURCES)
