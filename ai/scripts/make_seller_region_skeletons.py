"""실제 상세페이지 원문에서 화면 표지 줄만 남긴 뼈대 픽스처를 만든다.

    python scripts/make_seller_region_skeletons.py   (ai/ 에서 실행)

상용 원문은 저장소에 올리지 않는다(tests/fixtures/README.md). 대신 쇼핑몰 화면에 고정으로 붙는
표지 줄("장바구니", "상품 정보" 등)만 남기고 상품 글은 자리표시로 바꿔 커밋한다. 정제 코드를 고쳤을
때 실제 페이지 구조에서 결과가 바뀌는지 CI가 잡게 하기 위해서다.

뼈대마다 원문과 같은 결과(쇼핑몰, 잘림 여부, 제목 유무, 남는 표지 줄)가 나오는지 확인하고,
다르면 쓰지 않고 실패한다.
"""

import json
import re
import sys
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_ROOT))

from app.utils.seller_region import extract_seller_region  # noqa: E402

RAW_DIR = AI_ROOT / "tests" / "fixtures" / "_raw"
OUT_DIR = AI_ROOT / "tests" / "fixtures" / "seller_region"
TITLE = "판매자 상품 제목 자리표시 " + "가" * 80
BODY = "본문"

# 정제 코드가 보는 화면 표지. 상품 내용이 아니라 쇼핑몰 화면 글자만 둔다.
_EXACT = {
    "AliExpress", "Temu 앱 다운로드", "Coupang", "장바구니", "AI 상품 요약", "연관 상품", "상품 정보",
    "면책 조항", "판매자", "AliExpress의 약속", "카테고리", "팔로워", "제품 세부 정보",
}
# 뒤에 상품 글이 붙어 오는 표지는 앞부분만 남긴다.
_PREFIXES = ("구매자 질문", "모든 리뷰는", "가장 빠른 배송")
_REVIEW_COUNT = re.compile(r"리뷰 [\d,]+건")
# 쿠팡은 지원하지 않는다. "지원 밖 페이지는 그대로 넘어간다"를 보는 사례로 남긴다.
_UNSUPPORTED = ("coupang_direct_import",)


def skeleton(raw: str, title: str | None) -> str:
    out: list[str] = []
    for line in raw.replace("​", "").splitlines():
        s = line.strip()
        if not s:
            continue
        if title and s == title:
            out.append(TITLE)
        elif s in _EXACT or _REVIEW_COUNT.fullmatch(s):
            out.append(s)
        elif prefix := next((p for p in _PREFIXES if s.startswith(p)), None):
            out.append(prefix)
        elif not out or out[-1] != BODY:
            out.append(BODY)
    return "\n".join(out) + "\n"


def shape(text: str, title: str | None) -> list[str]:
    """남긴 구역을 뼈대 규칙으로 바꾼 줄 목록. 원문과 뼈대가 같은 경계로 잘렸는지 줄 단위로 비교한다."""
    return skeleton(text, title).splitlines()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    expected: dict[str, dict] = {}
    for path in sorted(RAW_DIR.glob("*.txt")):
        raw = path.read_text(encoding="utf-8")
        real = extract_seller_region(raw)
        if real.site is None and path.stem not in _UNSUPPORTED:
            continue
        text = skeleton(raw, real.title)
        skel = extract_seller_region(text)
        same = (
            skel.site == real.site
            and skel.trimmed == real.trimmed
            and (skel.title is not None) == (real.title is not None)
            and shape(skel.text, skel.title) == shape(real.text, real.title)
        )
        if not same:
            print(f"{path.stem}: 뼈대 결과가 원문과 다릅니다. 쓰지 않습니다.", file=sys.stderr)
            return 1
        (OUT_DIR / f"{path.stem}.txt").write_text(text, encoding="utf-8")
        expected[path.stem] = {
            "site": skel.site,
            "trimmed": skel.trimmed,
            "title": skel.title == TITLE,
            "kept": shape(skel.text, skel.title),
        }
        print(f"{path.stem}: {skel.site} 잘림={skel.trimmed} 남은 줄 {len(expected[path.stem]['kept'])}개")
    (OUT_DIR / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"뼈대 {len(expected)}개 저장: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
