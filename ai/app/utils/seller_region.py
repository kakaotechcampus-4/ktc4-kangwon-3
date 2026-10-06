"""상세페이지 원문에서 판매자가 쓴 구역만 남긴다 (#253).

복사한 상세페이지에는 판매자 글 말고도 쇼핑몰이 붙이는 글이 섞여 있다. AI 상품 요약,
연관 상품, 리뷰, 검색창, 배송·결제 안내가 그렇다. 이 글을 LLM과 규칙 레이어가 판매자 정보로
쓰면서 버그가 났다(#229 AI 요약, #251 연관 상품의 전압·용량, #252 검색창 글자를 카테고리로 씀).
프롬프트 문구로 막는 방식은 처음 보는 상품에서 약했으므로(#180) LLM에 넘기기 전에 코드로 자른다.

- 표지는 쇼핑몰 화면에 고정으로 붙는 문구("AI 상품 요약", "연관 상품", "상품 정보" 등)만 쓴다.
  상품 내용 단어를 표지로 쓰면 측정 픽스처에 맞춰진다(#180).
- 쇼핑몰을 알아봤는데 표지를 못 찾으면 원문을 그대로 돌려주고 경고를 남긴다. 화면 구조가
  바뀐 것을 알아채기 위해서다. 자르지 못해도 원래 동작과 같으므로 지금보다 나빠지지 않는다.
- 쇼핑몰을 알아보지 못한 입력(일부만 붙여 넣은 글 등)은 그대로 돌려준다.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SellerRegion:
    """정제 결과.

    text: LLM과 규칙 레이어에 넘길 텍스트. 자르지 못했으면 원문 그대로다.
    title: 판매자가 쓴 상품 제목 원문. 찾지 못했으면 None이다.
    site: 알아본 쇼핑몰("aliexpress", "temu", "coupang"). 모르면 None이다.
    trimmed: 구역을 실제로 잘랐는지.
    """

    text: str
    title: str | None
    site: str | None
    trimmed: bool


def extract_seller_region(text: str) -> SellerRegion:
    lines = text.replace("​", "").splitlines()
    stripped = [line.strip() for line in lines]
    head = [line for line in stripped if line][:20]

    for site, detect, cut in _SITES:
        if not detect(head):
            continue
        result = cut(lines, stripped)
        if result is None:
            logger.warning("%s 화면 표지를 찾지 못해 상세페이지 원문을 그대로 씁니다.", site)
            return SellerRegion(text=text, title=None, site=site, trimmed=False)
        kept, title = result
        return SellerRegion(text="\n".join(kept), title=title, site=site, trimmed=True)

    return SellerRegion(text=text, title=None, site=None, trimmed=False)


def _index(stripped: list[str], start: int, match) -> int | None:
    return next((i for i in range(start, len(stripped)) if match(stripped[i])), None)


def _first_text(lines: list[str], start: int, stop: int) -> str | None:
    return next((lines[i].strip() for i in range(start, stop) if lines[i].strip()), None)


# --- AliExpress -------------------------------------------------------------
# 순서: 상단 메뉴·검색창(장바구니까지) → 제목·가격·옵션 → AI 상품 요약 → 연관 상품 → 탭 줄 → 리뷰
#       → 상품 정보(스펙)·제품 설명 → 구매자 질문 → 면책 조항 이후(판매자 가게·플랫폼 안내·추천)
# 남기는 구간: 제목 구역, 두 번째 "상품 정보"(첫 번째는 탭 줄)부터 구매자 질문·면책 조항 전까지.

def _is_aliexpress(head: list[str]) -> bool:
    return "AliExpress" in head[:3]


def _cut_aliexpress(lines, stripped):
    cart = _index(stripped, 0, lambda s: s == "장바구니")
    if cart is None:
        return None
    top = cart + 1
    stop1 = _index(stripped, top, lambda s: s in ("AI 상품 요약", "연관 상품"))
    info = [i for i, s in enumerate(stripped) if s == "상품 정보"]
    if stop1 is None or len(info) < 2:
        return None
    start2 = info[1]
    stop2 = _index(stripped, start2, lambda s: s.startswith("구매자 질문") or s == "면책 조항")
    stop2 = len(lines) if stop2 is None else stop2
    return lines[top:stop1] + lines[start2:stop2], _first_text(lines, top, stop1)


# --- Temu ---------------------------------------------------------------------
# 순서: 상단 안내 → 카테고리 경로 → 제목 → 리뷰 → 판매자 가게 → 제품 세부 정보(스펙)·설명 사진 글
#       → 구매 상자(배송·가격 안내) → 푸터
# 남기는 구간: 카테고리 경로와 제목, 제품 세부 정보부터 구매 상자 전까지.

_TEMU_REVIEW_COUNT = re.compile(r"리뷰 [\d,]+건")


def _is_temu(head: list[str]) -> bool:
    return any("Temu" in line for line in head)


def _cut_temu(lines, stripped):
    category = _index(stripped, 0, lambda s: s == "카테고리")
    if category is None:
        return None
    top = category + 1
    stop1 = _index(
        stripped, top,
        lambda s: bool(_TEMU_REVIEW_COUNT.fullmatch(s)) or s.startswith("모든 리뷰는") or s == "팔로워",
    )
    start2 = _index(stripped, top, lambda s: s == "제품 세부 정보")
    if stop1 is None or start2 is None:
        return None
    # 구매 상자는 "가장 빠른 배송…" 또는 "판매자" 줄로 시작하고, 그 안에 배송·가격 안내가 있다.
    stop2 = _index(stripped, start2, lambda s: s.startswith("가장 빠른 배송") or s == "판매자")
    stop2 = len(lines) if stop2 is None else stop2
    # 경로 다음에 짧게 잘린 제목("…...")과 전체 제목이 함께 있다. 가장 긴 줄이 전체 제목이다.
    candidates = [lines[i].strip() for i in range(top, stop1) if lines[i].strip()]
    title = max(candidates, key=len) if candidates else None
    return lines[top:stop1] + lines[start2:stop2], title


# --- 쿠팡 -----------------------------------------------------------------------
# 순서: 상단 메뉴·검색창 → 분류 경로(쿠팡 홈 …) → 제목 → 가격·결제 → 옵션 → 쿠팡상품번호
#       → 다른 상품 광고·추천 → 상품상세 탭 → 필수 표기 정보 → 다른 고객이 함께 본 상품
# 남기는 구간: 분류 경로부터 쿠팡상품번호까지, 필수 표기 정보부터 접기 전까지.

_COUPANG_REVIEW_COUNT = re.compile(r"[\d,]+ 개 상품평")


def _is_coupang(head: list[str]) -> bool:
    return "Coupang" in head[:5]


def _cut_coupang(lines, stripped):
    top = _index(stripped, 0, lambda s: s == "쿠팡 홈")
    if top is None:
        return None
    product_no = _index(stripped, top, lambda s: s.startswith("쿠팡상품번호"))
    start2 = _index(stripped, top, lambda s: s == "필수 표기 정보")
    if product_no is None or start2 is None:
        return None
    # 표 바로 아래 "모든 로켓직구 상품은 관부가세 포함가!"는 모든 직구 상품에 붙는 쿠팡 안내다.
    stop2 = _index(stripped, start2, lambda s: s == "상품정보 접기" or s.startswith("모든 로켓직구"))
    stop2 = len(lines) if stop2 is None else stop2
    review = _index(stripped, top, lambda s: bool(_COUPANG_REVIEW_COUNT.fullmatch(s)))
    title = None
    if review is not None:
        title = next((lines[i].strip() for i in range(review - 1, top, -1) if lines[i].strip()), None)
    return lines[top:product_no + 1] + lines[start2:stop2], title


_SITES = (
    ("aliexpress", _is_aliexpress, _cut_aliexpress),
    ("temu", _is_temu, _cut_temu),
    ("coupang", _is_coupang, _cut_coupang),
)
