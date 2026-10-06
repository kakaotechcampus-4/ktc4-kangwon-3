"""조문 전문 조립 유틸을 실제 법제처 호출 없이 검증한다."""

from app.schemas.clients.law_response import LawArticle, LawItem, LawParagraph, LawSubItem
from app.utils.law_text import build_article_text


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
