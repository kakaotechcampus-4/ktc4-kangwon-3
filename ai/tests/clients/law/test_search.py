"""법제처 법령·시행법령·행정규칙·별표서식 검색 클라이언트를 실제 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.law import AdmrulSearchClient, EflawSearchClient, LawSearchClient, LicbylSearchClient
from app.schemas.clients.law_request import LawSearchRequest


def _xml(body: str):
    return lambda request: httpx.Response(200, text=body)


_LAW = (
    "<law><법령일련번호>{mst}</법령일련번호><법령ID>001732</법령ID><법령명한글>전파법</법령명한글>"
    "<법령구분명>법률</법령구분명><시행일자>{date}</시행일자><현행연혁코드>{status}</현행연혁코드>"
    "<법령상세링크>/DRF/lawService.do?OC=my-oc&amp;MST={mst}</법령상세링크></law>"
)


@pytest.mark.parametrize(("client_cls", "target"), [
    (LawSearchClient, "law"), (EflawSearchClient, "eflaw"), (AdmrulSearchClient, "admrul"), (LicbylSearchClient, "licbyl"),
])
def test_검색은_target과_검색어와_건수를_보낸다(wire, client_cls, target):
    client = client_cls(oc="my-oc")
    sent = wire(client, _xml("<LawSearch><totalCnt>0</totalCnt></LawSearch>"))

    client.fetch_raw(LawSearchRequest(query="전파법", display=5))

    params = sent[0].url.params
    assert sent[0].url.path == "/DRF/lawSearch.do"
    assert (params["target"], params["query"], params["display"]) == (target, "전파법", "5")
    assert "nw" not in params


def test_시행법령_검색은_연혁을_빼면_현행·시행예정_조건을_붙인다(wire):
    client = EflawSearchClient(oc="my-oc", include_history=False)
    sent = wire(client, _xml("<LawSearch><totalCnt>0</totalCnt></LawSearch>"))

    client.fetch_raw(LawSearchRequest(query="식품위생법", display=100))

    assert sent[0].url.params["nw"] == "2,3"


def test_시행법령_검색은_버전마다_현행·연혁·시행예정을_구분한다(wire):
    client = EflawSearchClient(oc="my-oc")
    wire(client, _xml(
        "<LawSearch><totalCnt>197</totalCnt>"
        + _LAW.format(mst="285531", date="20261022", status="시행예정")
        + _LAW.format(mst="276245", date="20260102", status="현행")
        + "</LawSearch>"
    ))

    result = client.fetch_parsed(LawSearchRequest(query="전파법"))

    assert result.total_count == 197
    assert [(i.mst, i.history_status) for i in result.items] == [("285531", "시행예정"), ("276245", "현행")]
    assert (result.items[1].law_id, result.items[1].law_type) == ("001732", "법률")


def test_검색_결과가_1건이어도_같은_모양으로_파싱한다(wire):
    client = LawSearchClient(oc="my-oc")
    wire(client, _xml("<LawSearch><totalCnt>3</totalCnt>" + _LAW.format(mst="276245", date="20260102", status="현행") + "</LawSearch>"))

    assert [i.mst for i in client.fetch_parsed(LawSearchRequest(query="전파법", display=1)).items] == ["276245"]


def test_행정규칙_검색은_현행_여부를_담는다(wire):
    # 시행 예정판도 "연혁"으로 옴 → "현행"만 믿을 수 있음
    client = AdmrulSearchClient(oc="my-oc")
    wire(client, _xml(
        "<AdmRulSearch><totalCnt>2</totalCnt>"
        "<admrul><행정규칙일련번호>2100000283202</행정규칙일련번호><행정규칙명>운용요령</행정규칙명>"
        "<시행일자>20261101</시행일자><현행연혁구분>연혁</현행연혁구분><행정규칙ID>34911</행정규칙ID></admrul>"
        "<admrul><행정규칙일련번호>2100000285148</행정규칙일련번호><행정규칙명>운용요령</행정규칙명>"
        "<시행일자>20260911</시행일자><현행연혁구분>현행</현행연혁구분><행정규칙ID>34911</행정규칙ID></admrul>"
        "</AdmRulSearch>"
    ))

    items = client.fetch_parsed(LawSearchRequest(query="운용요령")).items

    assert [(i.serial_number, i.enforce_date, i.history_status) for i in items] == [
        ("2100000283202", "20261101", "연혁"), ("2100000285148", "20260911", "현행")]


@pytest.mark.parametrize(("links", "expected"), [
    ("<별표서식파일링크>/LSW/flDownload.do?flSeq=1</별표서식파일링크><별표서식PDF파일링크>/LSW/flDownload.do?flSeq=2</별표서식PDF파일링크>",
     ("https://www.law.go.kr/LSW/flDownload.do?flSeq=1", "hwp")),
    ("<별표서식PDF파일링크>/LSW/flDownload.do?flSeq=2</별표서식PDF파일링크>", ("https://www.law.go.kr/LSW/flDownload.do?flSeq=2", "pdf")),
])
def test_별표서식_검색은_HWP를_우선해_파일_링크_하나를_담는다(wire, links, expected):
    client = LicbylSearchClient(oc="my-oc")
    wire(client, _xml(
        "<licBylSearch><totalCnt>1</totalCnt><licbyl><별표명>승계통보서</별표명><별표번호>004700</별표번호>"
        f"<별표종류>서식</별표종류><관련법령일련번호>287893</관련법령일련번호>{links}</licbyl></licBylSearch>"
    ))

    item = client.fetch_parsed(LawSearchRequest(query="승계")).items[0]

    assert (item.file_url, item.file_type) == expected
    assert (item.table_number, item.table_type, item.related_law_mst) == ("004700", "서식", "287893")
