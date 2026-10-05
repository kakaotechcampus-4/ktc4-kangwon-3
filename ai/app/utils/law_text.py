"""법령 조문 응답을 원문 순서의 전문 문자열로 조립. 조문 DB 적재·임베딩용."""

from ..schemas.clients.law_response import LawArticle


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
