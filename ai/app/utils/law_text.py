"""법령 본문 응답 후처리. 조문 전문 조립(DB 적재·임베딩용), 별표 하나 고르기."""

from ..schemas.clients.law_request import LicbylTextRequest
from ..schemas.clients.law_response import LawAnnex, LawArticle, LawTextResponse


def build_article_text(article: LawArticle) -> str:
    """조문내용 → 항 → 호 → 목 순서로 내용을 줄바꿈으로 잇는다.

    번호는 각 내용에 이미 포함되어 따로 붙이지 않음. 빈 내용은 건너뜀.

    Args:
        article: 항·호·목이 중첩된 조문.

    Returns:
        str: 조문 전문.
    """
    parts = [article.article_content]
    for paragraph in article.paragraphs:
        parts.append(paragraph.content)
        for item in paragraph.items:
            parts.append(item.content)
            parts.extend(sub_item.content for sub_item in item.sub_items)
    return "\n".join(part.strip() for part in parts if part and part.strip())


def select_annex(text: LawTextResponse, request: LicbylTextRequest) -> LawAnnex:
    """관련 법령 본문에서 별표·서식 검색 결과와 번호·종류가 맞는 별표 하나를 고른다.

    target=licbyl은 검색 전용이라 본문을 요청하면 HTML 껍데기가 옴.
    별표 본문은 관련 법령 본문(LawTextClient)에 함께 오므로, 그 결과에서 골라냄.

    Args:
        text: 관련 법령 본문 (request.related_law_mst로 LawTextClient 조회한 결과).
        request: 별표 검색 결과의 별표번호·별표종류.

    Returns:
        LawAnnex: 요청한 별표·서식 본문.

    Raises:
        RuntimeError: 관련 법령 본문에 요청한 별표가 없는 경우.
    """
    # 검색 결과 별표번호 "000300" = 본문 별표번호 "0003" + 별표가지번호 "00"
    number, branch = request.table_number[:4], request.table_number[4:]
    for annex in text.annexes:
        if (annex.annex_number, annex.annex_branch_number, annex.annex_type) == (number, branch, request.table_type):
            return annex

    # 빈 결과로 넘기면 "별표 내용 없음"으로 읽히므로 수신 실패와 같이 예외로 올림
    raise RuntimeError(
        f"법제처 별표 조회 실패: 관련 법령 본문에 요청한 별표가 없음 "
        f"(mst={request.related_law_mst}, 별표번호={request.table_number}, 종류={request.table_type})"
    )
