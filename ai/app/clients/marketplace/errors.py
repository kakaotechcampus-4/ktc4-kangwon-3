"""판매 사이트 클라이언트 예외."""


class BlockedUrlError(ValueError):
    """사이트 도메인 밖 주소로 요청하려 한 경우 (처음 주소·리다이렉트 모두). 요청은 보내지 않음."""


class PageTooLargeError(ValueError):
    """상품 페이지 응답이 크기 상한을 넘은 경우."""
