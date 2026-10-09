"""전기용품 근거 조회·품목표 파싱을 실제 법제처 응답 픽스처로 검증한다. 실제 API는 호출하지 않는다."""

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.schemas.clients.law_response import AdmrulSearchResponse
from app.tools.electrical.evidence import (
    NOTICE_ID, NOTICE_NAME, CachedEvidenceSource, DatabaseEvidenceSource, EvidenceUnavailable,
    LawApiEvidenceSource, LawLookupError, Scheme, article_text, compact, purchase_agent_status, select_version,
)

AS_OF = date(2026, 10, 7)


def _unit(evidence, scheme, sub_item):
    return next(block for block in evidence.blocks
                if block.scheme is scheme and any(compact(sub_item) == compact(item) for item in block.sub_items))


# -- 품목표 파싱 --

def test_세_품목표를_품목_단위로_나누고_삭제된_품목은_뺀다(electrical_evidence):
    counts = {scheme: sum(block.scheme is scheme for block in electrical_evidence.blocks) for scheme in Scheme}
    assert counts == {Scheme.CERTIFICATION: 33, Scheme.CONFIRMATION: 72, Scheme.SUPPLIER: 79}
    assert not any("삭제" in compact(block.items[0])[:6] for block in electrical_evidence.blocks)
    assert len({block.block_id for block in electrical_evidence.blocks}) == len(electrical_evidence.blocks)


def test_품목_비고와_분류_공통_비고가_해당_품목에_붙는다(electrical_evidence):
    fan = _unit(electrical_evidence, Scheme.CERTIFICATION, "선풍기")
    assert fan.category == "7. 전기기기"
    assert fan.items == ("저.팬, 레인지후드",)
    # 품목 자체 비고(1kW)와 분류 7 끝의 비고(10kW·방폭형)가 둘 다 걸린다.
    assert any("1kW" in note for note in fan.notes)
    assert any("10kW" in note and "방폭형" in note for note in fan.notes)
    # 인용문은 원문 문구를 그대로 담는다.
    assert "선풍기" in fan.section.text and "정격입력이 1kW 이하" in fan.section.text


@pytest.mark.parametrize("scheme,sub_item,category", [
    (Scheme.CERTIFICATION, "전기다리미", "7. 전기기기"),
    (Scheme.CONFIRMATION, "과일 껍질깎이", "7. 전기기기"),
    (Scheme.CONFIRMATION, "모니터", "10. 정보?통신?사무기기"),
    (Scheme.SUPPLIER, "비디오카메라", "9. 오디오?비디오응용기기"),
])
def test_분류명이_구간_중간에_적혀도_구간의_품목을_그_분류에_넣는다(electrical_evidence, scheme, sub_item, category):
    # 분류 칸의 이름은 세로 가운데 줄에 적혀, 같은 구간의 앞 품목들이 이름보다 먼저 나온다.
    assert _unit(electrical_evidence, scheme, sub_item).category == category


def test_칸이_합쳐진_비고는_앞_품목_묶음_전체에_걸린다(electrical_evidence):
    switch = _unit(electrical_evidence, Scheme.CERTIFICATION, "전자개폐기(정격전류가 300A 이하인 것에 한정한다)")
    other = next(block for block in electrical_evidence.blocks if block.items == ("가. 스위치",))
    assert switch.notes == other.notes
    assert "교류전압을 사용하는 제품에 한정" in switch.notes[0]


def test_깨진_번호_뒤의_세부품목도_나눈다(electrical_evidence):
    # 법제처 응답은 ⑯ 이후 번호를 "?"로 보낸다.
    mixer = _unit(electrical_evidence, Scheme.CERTIFICATION, "주서")
    assert "전기고기갈개" in mixer.sub_items and "기타주방용전동기기" in mixer.sub_items
    assert not any("?" in item for item in mixer.sub_items)


@pytest.mark.parametrize("scheme,sub_item,ac,dc", [
    (Scheme.CONFIRMATION, "전지", True, True),
    (Scheme.CONFIRMATION, "노트북컴퓨터", True, True),
    (Scheme.CERTIFICATION, "전격살충기", True, False),
    (Scheme.SUPPLIER, "공기청정기", False, True),
    (Scheme.CERTIFICATION, "선풍기", False, False),
    (Scheme.CERTIFICATION, "전기충전기", False, False),  # "30V 초과 … 한정"은 포함이 아니다.
])
def test_저전압_포함_비고를_교류_직류별로_찾는다(electrical_evidence, scheme, sub_item, ac, dc):
    blocks = [block for block in electrical_evidence.blocks
              if block.scheme is scheme and any(compact(sub_item) in compact(item) for item in block.sub_items)]
    assert blocks
    assert (blocks[0].includes_low_voltage_ac, blocks[0].includes_low_voltage_dc) == (ac, dc)


def test_표_끝의_공통_비고를_제도별로_따로_둔다(electrical_evidence):
    for scheme in Scheme:
        note = electrical_evidence.common_notes[scheme]
        assert "차량" in note.text and "전원으로 사용하는 구조의 것은" in note.text


# -- 버전 선택·본문 대조 --

def test_기준일에_시행_중인_버전을_고르고_미래_버전은_고르지_않는다(fake_law):
    evidence = LawApiEvidenceSource(fake_law).load(AS_OF)
    assert evidence.documents == [
        {"id": "008044", "version": "273575", "effective_date": "20260827"},
        {"id": "34911", "version": "2100000285148", "effective_date": "20260911"},
    ]
    later = LawApiEvidenceSource(fake_law).load(date(2026, 11, 2))
    assert later.documents[1]["version"] == "2100000283202"


def test_출처는_버전을_고정한_공개_주소이고_요청_키가_없다(fake_law):
    evidence = LawApiEvidenceSource(fake_law).load(AS_OF)
    urls = {block.section.source_url for block in evidence.blocks} | {evidence.rule_scope.source_url}
    assert urls == {
        "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000285148",
        "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=273575",
    }
    assert not any("OC=" in url for url in urls)


def _search(*items, total=None):
    return AdmrulSearchResponse(total_count=len(items) if total is None else total, items=[
        dict(rule_id=rule_id, name=NOTICE_NAME, serial_number=serial, enforce_date=day)
        for rule_id, serial, day in items
    ])


@pytest.mark.parametrize("result", [
    _search((NOTICE_ID, "1", "20261101")),                                 # 미래 버전뿐
    _search((NOTICE_ID, "1", "20260911"), (NOTICE_ID, "2", "20260911")),   # 같은 시행일 두 버전
    _search((NOTICE_ID, "1", "20260911"), total=5),                        # 목록 불완전
    _search(("99999", "1", "20260911")),                                   # 다른 문서
    _search((NOTICE_ID, "x1", "20260911")),                                # 일련번호 이상
])
def test_버전을_유일하게_정할_수_없으면_고르지_않는다(result):
    with pytest.raises(EvidenceUnavailable):
        select_version(result, name=NOTICE_NAME, identifier=NOTICE_ID, id_field="rule_id", name_field="name",
                       version_field="serial_number", as_of=AS_OF)


@pytest.mark.parametrize("field,value", [("document_id", "1"), ("name", "다른 고시"), ("enforce_date", "20200101")])
def test_검색과_본문의_식별정보가_다르면_근거로_쓰지_않는다(fake_law, field, value):
    body = fake_law.notice_bodies["2100000285148"]
    fake_law.notice_bodies["2100000285148"] = body.model_copy(update={field: value})
    with pytest.raises(EvidenceUnavailable):
        LawApiEvidenceSource(fake_law).load(AS_OF)


def test_필요한_별표가_없으면_근거로_쓰지_않는다(fake_law):
    body = fake_law.notice_bodies["2100000285148"]
    fake_law.notice_bodies["2100000285148"] = body.model_copy(update={"annexes": body.annexes[:2]})
    with pytest.raises(EvidenceUnavailable):
        LawApiEvidenceSource(fake_law).load(AS_OF)


# -- 조회 실패 분류 --

def test_법제처_응답_오류는_전용_예외로_바꾼다(fake_law):
    # LawClient는 API 오류 응답·XML 아님을 RuntimeError로 던진다.
    fake_law.error = RuntimeError("법제처 API 오류: OC=secret")
    with pytest.raises(LawLookupError) as caught:
        LawApiEvidenceSource(fake_law).load(AS_OF)
    assert "secret" not in str(caught.value)


def test_HTTP_오류는_호출자가_분류하도록_그대로_올린다(fake_law):
    request = httpx.Request("GET", "https://www.law.go.kr/DRF/lawSearch.do")
    fake_law.error = httpx.HTTPStatusError("x", request=request, response=httpx.Response(500, request=request))
    with pytest.raises(httpx.HTTPStatusError):
        LawApiEvidenceSource(fake_law).load(AS_OF)


# -- 캐시 --

class _CountingSource:
    def __init__(self, fail=False):
        self.loads, self.fail = 0, fail

    def load(self, as_of):
        self.loads += 1
        if self.fail:
            raise EvidenceUnavailable("x")
        return SimpleNamespace(as_of=as_of)


def test_같은_기준일은_한_번만_조회하고_유지시간이_지나면_다시_조회한다():
    now = [0.0]
    source = _CountingSource()
    cached = CachedEvidenceSource(source, ttl_seconds=10, clock=lambda: now[0])
    first = cached.load(AS_OF)
    assert cached.load(AS_OF) is first and source.loads == 1
    now[0] = 11
    cached.load(AS_OF)
    assert source.loads == 2
    cached.load(date(2026, 10, 8))
    assert source.loads == 3


def test_조회_실패는_캐시하지_않는다():
    source = _CountingSource(fail=True)
    cached = CachedEvidenceSource(source)
    for _ in range(2):
        with pytest.raises(EvidenceUnavailable):
            cached.load(AS_OF)
    assert source.loads == 2


# -- 기타 --

def test_항_아래_호가_중첩된_조문_응답도_전문을_모은다():
    # PR #248 이후 응답 형태: 항(paragraphs) 아래 호(items)·목(sub_items)이 중첩된다.
    sub = SimpleNamespace(content="가. 목")
    item = SimpleNamespace(content="1. 호", items=[], sub_items=[sub])
    paragraph = SimpleNamespace(content="① 항", items=[item], sub_items=[])
    article = SimpleNamespace(article_number="3", article_branch_number=None, article_content="제3조(범위)",
                              paragraphs=[paragraph])
    assert article_text(SimpleNamespace(articles=[article]), 3) == "제3조(범위) ① 항 1. 호 가. 목"


# -- 구매대행 특례 (시행규칙 별표 13) --

def test_별표13에서_안전인증_안전확인_전기용품_목록만_잘라_낸다(electrical_evidence):
    parts = electrical_evidence.purchase_agent
    assert set(parts) == {Scheme.CERTIFICATION, Scheme.CONFIRMATION}
    assert "전기액체가열기기" in compact(parts[Scheme.CERTIFICATION].text)
    assert "생활용품" not in parts[Scheme.CERTIFICATION].text[30:]  # 2호(생활용품)는 넣지 않는다
    assert "노트북컴퓨터" in compact(parts[Scheme.CONFIRMATION].text)
    assert parts[Scheme.CERTIFICATION].source_url.startswith("https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=")


@pytest.mark.parametrize("block_id,status", [
    ("cert-07-05", "listed"),                  # 전기액체가열기기(전기포트)
    ("cert-07-15", "listed"),                  # 팬
    ("cert-10-01", "listed_with_exclusion"),   # 직류전원장치(휴대전화 전지 충전기는 제외)
    ("cert-07-06", "listed_with_exclusion"),   # 전기담요 및 매트(전기침대는 제외)
    ("conf-10-12", "unmatched"),               # 전지(충전지) — 이름으로 못 찾음. "특례 없음"으로 확정하지 않는다
    ("cert-02-01", "unmatched"),               # 스위치: "전기기기용 스위치 대상 없음" 분류명에 걸리지 않는다
    ("cert-07-17", "similar_clause"),          # 그 밖에 유사한 기기
    ("sdoc-07-05", "unknown"),                 # 공급자적합성확인은 법 제35조 목록이 없다
])
def test_품목_행이_구매대행_특례_목록에_있는지_이름으로_찾는다(electrical_evidence, block_id, status):
    block = electrical_evidence.block(block_id)
    assert purchase_agent_status(block, electrical_evidence.purchase_agent.get(block.scheme))[0] == status


def test_별표13이_없으면_목록을_비우고_품목표는_그대로_쓴다(fake_law):
    fake_law.rule_body.annexes = []
    evidence = LawApiEvidenceSource(fake_law).load(AS_OF)
    assert evidence.purchase_agent == {}
    assert len(evidence.blocks) == 184


def test_DB_근거_경로는_구현_전까지_명시적으로_실패한다():
    with pytest.raises(NotImplementedError):
        DatabaseEvidenceSource(session_factory=None).load(AS_OF)
