"""식약 근거(식품위생법·수입식품법·의료기기법·품목·등급 고시) 읽기를 실제 법제처 응답 픽스처로 확인한다."""

import pytest

from app.tools.common.law import EvidenceUnavailable
from app.tools.food_drug.evidence import load_food_drug_evidence, parse_device_items
from app.tools.food_drug.search import rank_devices

from .conftest import AS_OF


def test_품목_등급_별표를_품목_행으로_나누고_삭제된_품목은_뺀다(food_drug_evidence):
    devices = food_drug_evidence.devices
    assert len(devices) == 2168
    assert {item.grade for item in devices} == {1, 2, 3, 4}
    assert all(item.item_id[0] in "ABC" for item in devices)  # (D)(E)는 삭제된 분류
    first = devices[0]
    assert (first.item_id, first.name, first.grade, first.group) == ("A01010.01", "범용 수동식 진료대", 1, "진료대와 수술대")
    assert first.english.startswith("Table") and first.definition == "일반적으로 사용하는 수동식 진료대"


def test_품목_순위는_품목명과_정의로_고른다(food_drug_evidence):
    found = rank_devices(food_drug_evidence.devices, ["적외선 체온계"], top_k=3)
    assert [item.name for item in found][:2] == ["귀 적외선 체온계", "피부 적외선 체온계"]
    assert all(item.grade == 2 for item in found)


def test_판단에_쓰는_항과_호만_잘라_인용한다(food_drug_evidence):
    evidence = food_drug_evidence
    assert evidence.food_definition.text.startswith('4. "기구"란') and "식품첨가물에 직접 닿는" in evidence.food_definition.text
    assert "공유주방" not in evidence.food_definition.text  # 5의2호부터는 자른다
    assert evidence.food_definition.label == "제2조 제4호·제5호"
    assert "인터넷 구매 대행업" in evidence.import_business.text
    assert evidence.import_report.text.startswith("① 영업자가 판매를 목적으로") and "②" not in evidence.import_report.text
    assert evidence.device_misleading.text.startswith("⑦ 누구든지") and "잘못 인식될 우려" in evidence.device_misleading.text
    assert "자가 사용용" in evidence.device_exemption.text


def test_출처는_버전을_고정한_공개_주소다(food_drug_evidence):
    source = food_drug_evidence.device_import.source()
    assert source.source_name == "법제처 국가법령정보" and source.law_name == "의료기기법"
    assert source.source_url == "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=285343"
    assert all("OC=" not in item["url"] for item in food_drug_evidence.documents())


def test_기준일에_시행_중인_버전을_고른다(fake_law):
    load_food_drug_evidence(fake_law, AS_OF)
    assert ("get_law_text", "999999") not in fake_law.calls


def test_잘라_낼_문구가_없으면_근거로_쓰지_않는다(fake_law):
    body = fake_law.law_bodies["285343"]
    article = next(item for item in body.articles if item.article_number == "26")
    article.paragraphs = [paragraph for paragraph in article.paragraphs if not paragraph.content.startswith("⑦")]
    with pytest.raises(EvidenceUnavailable, match="⑦"):
        load_food_drug_evidence(fake_law, AS_OF)


def test_품목_행이_없는_별표는_근거로_쓰지_않는다():
    with pytest.raises(EvidenceUnavailable):
        parse_device_items("[별표 1]\n의료기기 품목 및 품목별 등급\nA22010.01  <삭제>(2020.5.1.)")


# -- 화장품·건강기능식품 근거 --

def test_기능성화장품_범위를_시행규칙_제2조_호별로_읽는다(food_drug_evidence):
    types = food_drug_evidence.functional_types
    assert [item.number for item in types] == list(range(1, 12))
    assert "미백" in types[0].text and "자외선" in types[4].text and "튼살" in types[10].text
    assert food_drug_evidence.functional(5).number == 5 and food_drug_evidence.functional(12) is None


def test_사용할_수_없는_원료_별표를_원료_행으로_나눈다(food_drug_evidence):
    banned = food_drug_evidence.banned
    assert len(banned) == 1077
    guanethidine = next(row for row in banned if row.name == "구아네티딘 및 그 염류")
    # 같은 원료의 CAS 행이 여러 개면 화학물질명을 행마다 나눈다.
    assert guanethidine.cas == ("55-65-2", "76487-49-5", "645-43-2")
    assert guanethidine.chemicals == ("구아네티딘", "구아네티딘하이드로클로라이드", "구아네티딘 설페이트")


@pytest.mark.parametrize("ingredient, name", [
    ("수은", "수은 및 그 화합물"),                       # "및 그 화합물"을 뗀 이름
    ("구아네티딘 설페이트", "구아네티딘 및 그 염류"),     # 화학물질명 칸
    ("갈란타민", "갈란타민"),
])
def test_성분명이_원료명이나_화학물질명과_같으면_찾는다(food_drug_evidence, ingredient, name):
    assert food_drug_evidence.banned_match(ingredient).name == name


@pytest.mark.parametrize("ingredient", ["정제수", "글리세린", "나이아신아마이드", "수은함유"])
def test_이름이_다르면_찾지_않는다(food_drug_evidence, ingredient):
    assert food_drug_evidence.banned_match(ingredient) is None


def test_화장품_건강기능식품_조문은_판단에_쓰는_호만_인용한다(food_drug_evidence):
    evidence = food_drug_evidence
    assert evidence.cosmetic_definition.text.startswith('1. "화장품"이란') and "의약품" in evidence.cosmetic_definition.text
    assert "수입대행형 거래" in evidence.cosmetic_business_scope.text
    assert evidence.cosmetic_business_scope.label == "제2조 제11호"
    assert "수입대행형 거래" in evidence.cosmetic_sale_ban.text and "코뿔소" not in evidence.cosmetic_sale_ban.text
    assert "건강기능식품" in evidence.imported_scope.text
    assert evidence.health_food.text.startswith('1. "건강기능식품"이란') and '"기능성"이란' in evidence.health_food.text
