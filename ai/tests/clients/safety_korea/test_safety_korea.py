"""SafetyKorea 인증·리콜 클라이언트 5개를 실제 호출 없이 검증한다."""

import httpx
import pytest

from app.clients.safety_korea import (
    CertDetailClient,
    CertSearchClient,
    ForeignRecallSearchClient,
    RecallDetailClient,
    RecallSearchClient,
)
from app.schemas.clients.safety_korea_request import (
    CertDetailRequest,
    CertSearchRequest,
    ForeignRecallSearchRequest,
    RecallDetailRequest,
    RecallSearchRequest,
)


def _json(result_data, code="2000", msg="Success"):
    return lambda request: httpx.Response(200, json={"resultCode": code, "resultMsg": msg, "resultData": result_data})


def test_요청에는_AuthKey_헤더와_검색_구분을_보낸다(wire):
    client = CertSearchClient(auth_key="secret")
    sent = wire(client, _json([]))

    client.fetch_raw(CertSearchRequest(condition_key="productName", condition_value="전기포트"))

    assert sent[0].headers["AuthKey"] == "secret"
    assert (sent[0].url.params["conditionKey"], sent[0].url.params["conditionValue"]) == ("productName", "전기포트")


def test_인증번호_검색은_요청_번호와_정확히_일치하는_인증만_남긴다(wire):
    # 필터가 무시된 응답의 첫 항목을 믿으면 다른 제품의 인증 상태를 답함 (#185)
    client = CertSearchClient(auth_key="k")
    wire(client, _json([{"certNum": "YU102511-26007"}, {"certNum": "SU073007-26001", "certState": "적합"}]))

    result = client.fetch_parsed(CertSearchRequest(condition_key="certNum", condition_value="SU073007-26001"))

    assert [(i.certification_number, i.certification_status) for i in result.items] == [("SU073007-26001", "적합")]


def test_인증번호_외_검색은_결과를_거르지_않는다(wire):
    client = CertSearchClient(auth_key="k")
    wire(client, _json([{"certNum": "A"}, {"certNum": "B"}]))

    result = client.fetch_parsed(CertSearchRequest(condition_key="productName", condition_value="전기포트"))

    assert [i.certification_number for i in result.items] == ["A", "B"]


def test_인증_상세는_명세_의미대로_풀어_쓴_필드로_옮긴다(wire):
    client = CertDetailClient(auth_key="k")
    wire(client, _json({
        "certUid": 6371838, "certOrganName": "한국산업기술시험원(KTL)", "certNum": "SU073007-26001",
        "certDiv": "전기용품 및 생활용품 안전관리법 대상>안전인증대상 전기용품", "certDate": "20260707",
        "firstCertNum": "SU073007-26001", "importDiv": "수입", "makerCntryName": "중국", "signDate": "20260710",
        "remark": "상세", "factories": [{"makerName": "공장", "makerCntryName": "중국"}],
    }))

    item = client.fetch_parsed(CertDetailRequest(certification_number="SU073007-26001"))

    assert (item.certification_id, item.certification_body_name) == (6371838, "한국산업기술시험원(KTL)")
    assert (item.certification_type, item.certified_date) == ("전기용품 및 생활용품 안전관리법 대상>안전인증대상 전기용품", "20260707")
    assert (item.original_certification_number, item.import_type, item.manufacture_country) == ("SU073007-26001", "수입", "중국")
    assert (item.registered_date, item.remarks) == ("20260710", "상세")
    assert item.factories[0].manufacturer_name == "공장"


def test_국내리콜과_국외리콜은_같은_원문_키라도_명세_의미대로_나눠_담는다(wire):
    # accidentCaseDscr: 국내는 위해 정보, 국외는 소비자 행동요령
    domestic = RecallDetailClient(auth_key="k")
    wire(domestic, _json({"recallUid": "1", "recallModelCnt": 2, "harmDscr": "결함", "accidentCaseDscr": "위해",
                          "publishActionDscr": "행동요령", "recallFiles": [{"fileDiv": "부분사진", "imageUrl": "u"}]}))
    foreign = ForeignRecallSearchClient(auth_key="k")
    wire(foreign, _json([{"fRecallUid": "2", "recallModelCnt": "1", "violateDscr": "위해",
                          "accidentCaseDscr": "행동요령", "publishActionDscr": "소비자회수"}]))

    d = domestic.fetch_parsed(RecallDetailRequest(recall_id="1"))
    f = foreign.fetch_parsed(ForeignRecallSearchRequest(condition_key="recallProductName", condition_value="x")).items[0]

    assert (d.defect_description, d.hazard_description, d.consumer_guidance) == ("결함", "위해", "행동요령")
    assert (f.hazard_description, f.consumer_guidance, f.action_taken) == ("위해", "행동요령", "소비자회수")
    # 모델 개수: 국내는 숫자, 국외는 문자열로 와도 int
    assert (d.recall_model_count, f.recall_model_count) == (2, 1)
    assert d.recall_images[0].file_type == "부분사진"


def test_원문_값의_앞뒤_공백을_지우고_정보_없음_표시는_None으로_바꾼다(wire):
    client = ForeignRecallSearchClient(auth_key="k")
    wire(client, _json([{"fRecallUid": "2", "makerName": "-", "violateDscr": "화재 위험\n", "recallBrandName": "Zwilling\xa0"}]))

    item = client.fetch_parsed(ForeignRecallSearchRequest(condition_key="recallProductName", condition_value="x")).items[0]

    assert (item.manufacturer_name, item.hazard_description, item.recall_brand_name) == (None, "화재 위험", "Zwilling")


def test_인증_실패는_302로_오고_예외로_올린다(wire):
    client = CertSearchClient(auth_key="invalid")
    wire(client, lambda request: httpx.Response(302, headers={"location": "/openapi/api/error/accessDeniedByKey.json"}))

    with pytest.raises(RuntimeError, match="인증 실패"):
        client.fetch_raw(CertSearchRequest(condition_key="productName", condition_value="x"))


@pytest.mark.parametrize(("code", "data"), [("2000", [{"certNum": "A"}]), (2000, [{"certNum": "A"}]), ("2004", None)])
def test_결과코드_2000과_2004는_정상으로_본다(wire, code, data):
    client = CertSearchClient(auth_key="k")
    wire(client, _json(data, code=code))

    assert len(client.fetch_parsed(CertSearchRequest(condition_key="productName", condition_value="x")).items) == len(data or [])


@pytest.mark.parametrize(("code", "msg"), [("4001", "Invalid IP"), ("4005", "Invalid Parameter"), (5000, "Internal Server Error")])
def test_HTTP_200이어도_오류_결과코드면_예외를_올린다(wire, code, msg):
    client = CertSearchClient(auth_key="k")
    wire(client, _json(None, code=code, msg=msg))

    with pytest.raises(RuntimeError, match=f"resultCode={code}"):
        client.fetch_parsed(CertSearchRequest(condition_key="productName", condition_value="x"))


@pytest.mark.parametrize("client_cls", [RecallSearchClient, ForeignRecallSearchClient])
@pytest.mark.parametrize("value", ["2015", "2024-03", "20240101~20241231"])
def test_리콜_공표일_검색은_최근_5년_밖이거나_형식이_틀리면_요청_전에_거부한다(wire, client_cls, value):
    # 기간 경계 계산은 utils/date_range 테스트에서 기준일을 고정해 따로 확인
    client = client_cls(auth_key="k")
    sent = wire(client, _json([]))
    request_cls = RecallSearchRequest if client_cls is RecallSearchClient else ForeignRecallSearchRequest

    with pytest.raises(ValueError):
        client.fetch_raw(request_cls(condition_key="publishDate", condition_value=value))
    assert sent == []


def test_리콜_공표일_외_검색은_연도와_상관없이_보낸다(wire):
    client = RecallSearchClient(auth_key="k")
    sent = wire(client, _json([]))

    client.fetch_raw(RecallSearchRequest(condition_key="recallProductName", condition_value="2019"))

    assert len(sent) == 1
