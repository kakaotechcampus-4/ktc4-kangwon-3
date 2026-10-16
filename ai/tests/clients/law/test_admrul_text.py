"""법제처 행정규칙 본문 클라이언트를 실제 호출 없이 검증한다."""

import re

import httpx
import pytest

from app.clients.law import AdmrulTextClient
from app.schemas.clients.law_request import LawTextRequest
from app.utils.law_text import build_article_text


def _info(article_format: str = "Y", current: str = "Y") -> str:
    return (
        "<행정규칙기본정보><행정규칙일련번호>2100000282502</행정규칙일련번호><행정규칙ID>35531</행정규칙ID>"
        "<행정규칙명>세관장확인물품 지정고시</행정규칙명><행정규칙종류>고시</행정규칙종류>"
        "<발령일자>20260716</발령일자><발령번호>2026-46</발령번호><제개정구분명>일부개정</제개정구분명>"
        f"<시행일자>20260716</시행일자><소관부처명>관세청</소관부처명><현행여부>{current}</현행여부>"
        f"<조문형식여부>{article_format}</조문형식여부></행정규칙기본정보>"
    )


def _rule(contents: list[str], *, article_format: str = "Y", current: str = "Y", extra: str = "") -> str:
    body = "".join(f"<조문내용><![CDATA[{c}]]></조문내용>" for c in contents)
    return f"<AdmRulService>{_info(article_format, current)}{body}{extra}</AdmRulService>"


def _fetch(wire, body: str):
    client = AdmrulTextClient(oc="my-oc")
    sent = wire(client, lambda request: httpx.Response(200, text=body))
    return client.fetch_parsed(LawTextRequest(mst="2100000282502")), sent


def test_본문_요청은_target_admrul과_ID를_보낸다(wire):
    _, sent = _fetch(wire, _rule([]))

    assert (sent[0].url.params["target"], sent[0].url.params["ID"]) == ("admrul", "2100000282502")


def test_기본정보는_버전키·종류·발령정보·현행·조문형_여부를_담는다(wire):
    result, _ = _fetch(wire, _rule([], current="N"))

    assert (result.serial_number, result.document_id, result.name) == ("2100000282502", "35531", "세관장확인물품 지정고시")
    assert (result.rule_type, result.issue_date, result.issue_number, result.revision_type) == ("고시", "20260716", "2026-46", "일부개정")
    assert (result.enforce_date, result.department) == ("20260716", "관세청")
    assert (result.is_current, result.is_article_format) == (False, True)


def test_조문형_고시는_구획_제목을_빼고_조문번호·제목·소속을_뽑는다(wire):
    result, _ = _fetch(wire, _rule([
        "제1장 공통사항", "제1절 총칙",
        "제1조(목적) 이 요령은 …",
        "제6조의2(전문위원회 검토) 국가기술표준원장은 …",
        "제2절 안전인증", "제7조(신청) 신청한다.",
    ]))

    assert [(a.article_number, a.article_branch_number, a.article_title, a.headings) for a in result.articles] == [
        ("1", None, "목적", ["제1장 공통사항", "제1절 총칙"]),
        ("6", "2", "전문위원회 검토", ["제1장 공통사항", "제1절 총칙"]),
        ("7", None, "신청", ["제1장 공통사항", "제2절 안전인증"]),
    ]


def test_조문형_고시_조문은_앞문장과_항·호·목으로_나눈다(wire):
    content = ("제2조(정의) ① 이 고시에서 사용하는 용어의 뜻은 다음 각 호와 같다.\n\n"
               "  1. \"제조자\"라 함은 …\n  1의2. \"제조국가\"라 함은 …\n"
               "    가. 첫째 목\n    이어지는 줄\n"
               "  ② 둘째 항")
    article = _fetch(wire, _rule([content]))[0].articles[0]

    assert article.article_content == "제2조(정의)"
    assert [p.number for p in article.paragraphs] == ["①", "②"]
    items = article.paragraphs[0].items
    assert [i.number for i in items] == ["1.", "1의2."]
    # 머리 없는 줄은 바로 앞 요소에 이어 붙임
    assert items[1].sub_items[0].content == "가. 첫째 목\n이어지는 줄"


def test_항_없이_호만_있는_조문은_번호_없는_항_아래에_호를_담는다(wire):
    article = _fetch(wire, _rule(["제3조(대상) 대상은 다음과 같다.\n  1. 첫째\n  2. 둘째"]))[0].articles[0]

    assert article.article_content == "제3조(대상) 대상은 다음과 같다."
    assert (article.paragraphs[0].number, [i.number for i in article.paragraphs[0].items]) == (None, ["1.", "2."])


def test_나눈_조문을_다시_이으면_원문과_글자가_같다(wire):
    contents = ["제3조(요건신청 방법) ① 첫째 항.\n  ② 둘째 항\n    1. 호\n      가. 목",
                "제5조(효력) 효력은 접수 시점으로 한다."]
    articles = _fetch(wire, _rule(contents))[0].articles

    normalize = lambda text: re.sub(r"\s+", "", text)
    assert [normalize(build_article_text(a)) for a in articles] == [normalize(c) for c in contents]


def test_비조문형_고시는_본문을_한_덩어리_그대로_담는다(wire):
    result, _ = _fetch(wire, _rule(["1. 적용범위\n이 기준은 …\n2. 용어"], article_format="N"))

    assert len(result.articles) == 1
    assert (result.articles[0].article_number, result.articles[0].paragraphs) == (None, [])
    assert result.articles[0].article_content.startswith("1. 적용범위")


def test_첨부파일은_같은_문서의_형식을_묶어_파싱_쉬운_링크_하나만_담는다(wire):
    attachments = (
        "<첨부파일>"
        "<첨부파일명>수입요건_260716.xlsx</첨부파일명><첨부파일링크>http://law.go.kr/flDownload.do?flSeq=1</첨부파일링크>"
        "<첨부파일명>고시전문_최종.hwpx\n</첨부파일명><첨부파일링크>http://law.go.kr/flDownload.do?flSeq=2</첨부파일링크>"
        "<첨부파일명>고시전문_최종.pdf</첨부파일명><첨부파일링크>http://law.go.kr/flDownload.do?flSeq=3</첨부파일링크>"
        "</첨부파일>"
    )
    result, _ = _fetch(wire, _rule([], extra=attachments))

    assert [(a.name, a.file_type, a.file_url) for a in result.attachments] == [
        ("수입요건_260716", "xlsx", "http://law.go.kr/flDownload.do?flSeq=1"),
        ("고시전문_최종", "hwpx", "http://law.go.kr/flDownload.do?flSeq=2"),
    ]


def test_첨부파일이_없으면_빈_목록이다(wire):
    assert _fetch(wire, _rule([]))[0].attachments == []


@pytest.mark.parametrize("body", [
    "<Law>일치하는 행정규칙이 없습니다. 행정규칙명을 확인하여 주십시오.</Law>",
    "<!DOCTYPE html><html><body>" + "&nbsp;" * 10,
])
def test_본문을_받지_못한_응답은_수신_실패로_올린다(wire, body):
    with pytest.raises(RuntimeError, match="수신 실패"):
        _fetch(wire, body)


def test_작은_정상_행정규칙도_기본정보가_있으면_받는다(wire):
    # 1,366B 정상 행정규칙 존재 (크기로 판별 불가)
    result, _ = _fetch(wire, _rule(["세무공무원이 과세자료 조사를 위하여 열람하는 경우 수수료를 면제한다."], article_format="N"))

    assert result.name == "세관장확인물품 지정고시"
    assert len(result.articles) == 1
