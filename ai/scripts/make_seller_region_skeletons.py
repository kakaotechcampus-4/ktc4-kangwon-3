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
TITLE = "판매자 상품 제목 자리표시 (Temu는 구역에서 가장 긴 줄을 제목으로 찾으므로 이 줄을 일부러 길게 둔다)"
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


def _is_marker(line: str) -> bool:
    return line in _EXACT or bool(_REVIEW_COUNT.fullmatch(line)) or line.startswith(_PREFIXES)


def unknown_boundaries(raw: str, kept_text: str) -> list[str]:
    """원문에서 남긴 구간의 경계가 이 스크립트의 표지 줄인지 확인한다. 아니면 그 줄을 돌려준다.

    표지 목록에 없는 줄에서 자르면 뼈대에서는 그 줄이 `본문`으로 접혀, 원문과 뼈대의 모양이 같아 보여도
    정제 결과는 다르다. 정제 코드에 표지를 추가하고 위 목록(_EXACT·_PREFIXES)에 넣지 않은 경우다.
    """
    lines = [line.strip() for line in raw.replace("​", "").splitlines() if line.strip()]
    kept = [line.strip() for line in kept_text.splitlines() if line.strip()]
    # 남긴 줄은 원문 줄의 순서를 지킨 부분열이다. 같은 줄이 여러 번 나오면 남긴 쪽을 뒤에서부터 맞춘다
    # (첫 번째 "상품 정보"는 탭 줄이고 두 번째가 남는 구간의 시작이다).
    flags = [False] * len(lines)
    j = len(kept) - 1
    for i in range(len(lines) - 1, -1, -1):
        if j >= 0 and lines[i] == kept[j]:
            flags[i] = True
            j -= 1
    if j >= 0:
        return ["남긴 줄을 원문에서 순서대로 찾지 못함"]
    problems = []
    for i in range(len(lines) - 1):
        if flags[i] and not flags[i + 1] and not _is_marker(lines[i + 1]):
            problems.append(f"끝 경계 '{lines[i + 1][:20]}'")
        if not flags[i] and flags[i + 1] and not (_is_marker(lines[i]) or _is_marker(lines[i + 1])):
            problems.append(f"시작 경계 '{lines[i + 1][:20]}'")
    return problems


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
        if real.trimmed and (problems := unknown_boundaries(raw, real.text)):
            print(f"{path.stem}: 표지 목록에 없는 줄에서 잘렸습니다 {problems}. _EXACT·_PREFIXES에 표지를 추가하세요.",
                  file=sys.stderr)
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
