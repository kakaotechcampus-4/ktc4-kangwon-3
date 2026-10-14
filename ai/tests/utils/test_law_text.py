"""법령 본문 후처리 유틸(조문 전문 조립·별표 고르기)을 실제 법제처 호출 없이 검증한다."""

import pytest

from app.schemas.clients.law_request import LicbylTextRequest
from app.schemas.clients.law_response import LawAnnex, LawArticle, LawItem, LawParagraph, LawSubItem, LawTextResponse
from app.utils.law_text import build_article_text, select_annex


def test_조문_전문은_항_호_목을_원문_순서대로_잇는다():
    article = LawArticle(
        article_content="제4조(안전인증기관의 지정신청 등)",
        paragraphs=[
            LawParagraph(
                number="①",
                content="① 첫째 항",
                items=[LawItem(number="1.", content="1. 첫째 항의 1호")],
            ),
            LawParagraph(
                number="④",
                content="④ 넷째 항",
                items=[
                    LawItem(
                        number="1.",
                        content="1. 넷째 항의 1호",
                        sub_items=[LawSubItem(number="가.", content="가. 1호의 가목\n")],
                    )
                ],
            ),
        ],
    )

    assert build_article_text(article) == (
        "제4조(안전인증기관의 지정신청 등)\n"
        "① 첫째 항\n"
        "1. 첫째 항의 1호\n"
        "④ 넷째 항\n"
        "1. 넷째 항의 1호\n"
        "가. 1호의 가목"
    )


def test_항번호_없는_항은_빈_줄_없이_호부터_잇는다():
    article = LawArticle(
        article_content="제2조(정의) 용어의 뜻은 다음과 같다.",
        paragraphs=[
            LawParagraph(items=[LawItem(content="1. 첫째 용어"), LawItem(content="2. 둘째 용어")]),
        ],
    )

    assert build_article_text(article) == "제2조(정의) 용어의 뜻은 다음과 같다.\n1. 첫째 용어\n2. 둘째 용어"


def test_항이_없는_조문은_조문내용만_돌려준다():
    article = LawArticle(article_content="제1조(목적) 이 규칙은 위임된 사항을 규정한다.")

    assert build_article_text(article) == "제1조(목적) 이 규칙은 위임된 사항을 규정한다."


# 한 법령 안에 같은 번호(0003/00)의 별표와 서식이 따로 있음 (#184)
_SAME_NUMBER_ANNEXES = LawTextResponse(
    articles=[],
    annexes=[
        LawAnnex(annex_number="0003", annex_branch_number="00", annex_type="별표", annex_title="안전인증대상제품"),
        LawAnnex(annex_number="0003", annex_branch_number="00", annex_type="서식", annex_title="안전인증기관 지정신청서"),
    ],
)


@pytest.mark.parametrize(("table_type", "expected_title"), [("별표", "안전인증대상제품"), ("서식", "안전인증기관 지정신청서")])
def test_별표는_관련_법령_본문에서_번호와_종류가_맞는_것을_고른다(table_type, expected_title):
    # 검색 결과 별표번호 "000300" = 본문 별표번호 "0003" + 가지번호 "00"
    request = LicbylTextRequest(related_law_mst="273575", table_number="000300", table_type=table_type)

    assert select_annex(_SAME_NUMBER_ANNEXES, request).annex_title == expected_title


def test_관련_법령_본문에_요청한_별표가_없으면_빈_결과_대신_예외를_올린다():
    request = LicbylTextRequest(related_law_mst="273575", table_number="000400", table_type="별표")

    with pytest.raises(RuntimeError, match="요청한 별표가 없음"):
        select_annex(_SAME_NUMBER_ANNEXES, request)


@pytest.mark.parametrize("table_number", ["0003", "0003-00", "00030000"])
def test_별표번호는_6자리만_허용한다(table_number):
    with pytest.raises(ValueError):
        LicbylTextRequest(related_law_mst="273575", table_number=table_number, table_type="별표")
