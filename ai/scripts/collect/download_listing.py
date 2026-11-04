"""수집 북마클릿(collect_listing.js)이 내려 준 JSON을 평가용 상품 폴더로 푼다 (#567).

    # 한 상품: 본문 JSON, 그 뒤에 북마클릿이 새 탭으로 연 프레임에서 받은 JSON(있으면)
    python scripts/collect/download_listing.py <본문 json> [<프레임 json> ...] --out tests/fixtures/_raw/strat_01

    # 다운로드 폴더의 수집 JSON을 전부 번호 폴더로 (이미 내보낸 것은 건너뜀)
    python scripts/collect/download_listing.py --batch ~/Downloads --out-root tests/fixtures/_raw --prefix strat

상품 폴더에 남기는 것:
    text.txt             "더보기"를 펼친 뒤 글 (첫 줄은 "# 사이트 주소", 기존 _raw 규약)
    text_as_pasted.txt   펼치기 전 글. 실제 사용자가 Ctrl+A로 붙여 넣는 형태 (펼친 글과 다를 때만)
    description.txt      알리 shadow DOM 안의 설명 글 (일반 복사로는 안 딸려 옴, 있을 때만)
    img_NN.jpg           상세 설명 구역의 이미지 원본 (북마클릿이 기록한 화면 위치 순)
    listing.json         북마클릿 원본 기록 (표지 위치·펼침·프레임 진단 포함)

상세 설명 이미지만 남기는 규칙 (사이트별):
    temu        "제품 세부 정보" 표지 아래 ~ "관심 상품 둘러보기"/"인기 추천" 표지 위.
                연관 상품(alt "품목 사진 …")·판매자 아바타·배너 호스트 제외. 1600px JPEG로 받음.
    aliexpress  "개요"/"Description" 표지 아래 ~ "구매자 질문"/"면책 조항"/"함께 볼 만한 상품" 표지 위.
                alt가 있는 480×480은 연관 상품이라 제외. 썸네일 꼬리를 떼어 원본으로 받음.
표지가 없는 JSON은 페이지 전체를 보고, --min-top/--max-top으로 직접 범위를 줄 수 있다.

상용 원문이므로 결과는 저장소에 올리지 않는다 (_raw/는 git에서 제외).
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

Fetch = Callable[[str, str], tuple[bytes, str | None]]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
# 알리 CDN은 Accept에 webp·avif가 있으면 그 형식으로 바꿔 준다. 원본 JPEG/PNG만 받는다.
ACCEPT = "image/jpeg,image/png"
MIN_IMAGE_SIDE = 300
PAUSE_SECONDS = 0.5
PAGE_END = 10**9
# 북마클릿 파일 이름: <site>_<ISO 시각>.json
_COLLECTED_JSON = re.compile(r"^(temu|aliexpress)_\d{4}-\d{2}-\d{2}T.*\.json$")
# 알리 썸네일 주소: 원본 경로 뒤에 "_480x480q75.jpg_.avif" 같은 꼬리가 붙는다
_ALI_ORIGINAL = re.compile(r"^(.*?\.(?:jpg|jpeg|png|webp))(?:_.*)?$", re.IGNORECASE)
# 알리 썸네일 꼬리: "…jpg_480x480q75.jpg_.avif", "…png_960x960.png_.avif"
_ALI_THUMBNAIL_SUFFIX = re.compile(r"_\d+x\d+", re.IGNORECASE)
_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/avif": ".avif", "image/gif": ".gif"}

SITE_RULES: dict[str, dict] = {
    "temu": {
        "start": ("제품 세부 정보", "Product details"),
        "end": ("관심 상품 둘러보기", "인기 추천", "Explore your interests"),
        "junk_hosts": ("aimg.kwcdn.com", "commimg.kwcdn.com"),
    },
    "aliexpress": {
        "start": ("개요", "설명", "Description", "Overview"),
        "end": ("구매자 질문", "면책 조항", "함께 볼 만한 상품", "Customer Questions", "More to love", "Related products"),
        "junk_hosts": (),
    },
}


def _marker_top(markers: list[dict], names: tuple[str, ...], *, after: int = -1) -> int | None:
    for marker in markers:
        if marker["text"] in names and marker["top"] > after:
            return marker["top"]
    return None


def detail_range(site: str, markers: list[dict], *, min_top: int | None = None, max_top: int | None = None) -> tuple[int, int]:
    """상세 설명 이미지가 있는 화면 세로 범위 [low, high).

    사이트 규칙의 시작 표지와, 그 아래 처음 나오는 끝 표지로 정한다. 직접 준 값이 우선.

    Args:
        site: 북마클릿이 기록한 사이트 이름.
        markers: 북마클릿이 기록한 표지 목록 ({"text", "top"}).
        min_top: 직접 준 시작 위치.
        max_top: 직접 준 끝 위치.

    Returns:
        tuple[int, int]: 시작·끝 위치. 표지가 없으면 (0, 페이지 끝).
    """
    rule = SITE_RULES.get(site, {})
    start = _marker_top(markers, rule.get("start", ()))
    end = _marker_top(markers, rule.get("end", ()), after=start if start is not None else -1)
    low = min_top if min_top is not None else (start if start is not None else 0)
    high = max_top if max_top is not None else (end if end is not None else PAGE_END)
    return low, high


def _is_ali_overflowed_description(site: str, image: dict, low: int) -> bool:
    """알리 "개요"가 접힌 채라 끝 표지 아래로 밀려난 설명 이미지인지.

    접힌 구역은 overflow만 가려서 안쪽 이미지의 레이아웃 위치가 끝 표지("구매자 질문")를 넘어간다.
    설명 이미지는 썸네일 꼬리(`_480x480…`)가 없는 원본 주소이고 alt가 없어, 연관 상품(alt 있음)·
    카테고리 타일(썸네일 꼬리)과 구분된다. 갤러리 원본은 구역 시작 위에 있어 low로 걸러진다.
    """
    if site != "aliexpress" or image["top"] < low or image["alt"]:
        return False
    bare = image["src"].split("?")[0]
    return not _ALI_THUMBNAIL_SUFFIX.search(bare) and bool(_ALI_ORIGINAL.match(bare))


def keep_image(site: str, image: dict, low: int, high: int, *, is_frame: bool = False) -> str | None:
    """상세 설명 이미지로 남기면 None, 거르면 그 이유.

    Args:
        site: 사이트 이름.
        image: 북마클릿이 기록한 이미지 ({"src", "width", "height", "top", "alt", "lazy"}).
        low: 상세 구역 시작.
        high: 상세 구역 끝.
        is_frame: 설명 프레임 탭에서 받은 이미지인지. 그러면 구역을 보지 않는다.

    Returns:
        str | None: 거른 이유. 남기면 None.
    """
    if not image.get("lazy") and max(image["width"], image["height"]) < MIN_IMAGE_SIDE:
        return "작음"
    if is_frame:
        return None
    if not (low <= image["top"] < high) and not _is_ali_overflowed_description(site, image, low):
        return "상세 구역 밖"
    rule = SITE_RULES.get(site, {})
    host = urlparse(image["src"]).hostname or ""
    if host in rule.get("junk_hosts", ()) or "supplier-public-tag" in image["src"]:
        return "배너·아바타"
    if site == "temu" and image["alt"].lower().startswith(("품목 사진", "item picture")):
        return "연관 상품"
    if site == "aliexpress" and image["alt"] and image["width"] == 480 and image["height"] == 480:
        return "연관 상품"
    return None


def normalize_image_url(site: str, url: str) -> str:
    """썸네일 주소를 원본(또는 충분히 큰) 주소로 바꾼다.

    Args:
        site: 사이트 이름.
        url: 북마클릿이 기록한 이미지 주소.

    Returns:
        str: 받을 주소. 모르는 사이트는 그대로.
    """
    bare = url.split("?")[0]
    if site == "temu" and "kwcdn.com" in url:
        return bare + "?imageView2/2/w/1600/q/85"
    if site == "aliexpress" and ("alicdn" in url or "aliexpress-media" in url):
        match = _ALI_ORIGINAL.match(bare)
        return match.group(1) if match else bare
    return url


def extension_of(url: str, content_type: str | None) -> str:
    """저장 파일 확장자. 응답 content-type을 우선하고, 없으면 주소 경로를 본다."""
    by_type = _EXTENSIONS.get((content_type or "").split(";")[0].strip())
    if by_type:
        return by_type
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".bin"


def fetch_image(url: str, referer: str) -> tuple[bytes, str | None]:
    """이미지 한 장을 받는다. (본문, content-type)"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": referer, "Accept": ACCEPT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(), response.headers.get("Content-Type")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def export_listing(
    main_data: dict,
    frame_datas: list[dict],
    out_dir: Path,
    *,
    fetch: Fetch = fetch_image,
    min_top: int | None = None,
    max_top: int | None = None,
    pause: float = 0.0,
) -> dict:
    """본문 JSON(과 프레임 JSON)을 상품 폴더로 푼다.

    Args:
        main_data: 상품 페이지에서 받은 JSON.
        frame_datas: 설명 프레임 탭에서 받은 JSON들. 이미지는 전부 상세 설명으로 본다.
        out_dir: 상품 폴더.
        fetch: 이미지를 받는 함수 (테스트에서 바꿔 끼움).
        min_top: 직접 준 상세 구역 시작.
        max_top: 직접 준 상세 구역 끝.
        pause: 이미지 사이 쉬는 시간(초). CDN에 몰아치지 않으려고.

    Returns:
        dict: saved(저장 수), dropped(이유별 거른 수), failures(받기 실패 주소), range(상세 구역).
    """
    site = main_data["site"]
    header = f"# {site} {main_data['url']}\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    # 같은 폴더에 다시 내보낼 때 이전 실행의 이미지가 번호 뒤에 남지 않게 먼저 지운다
    for stale in out_dir.glob("img_*"):
        stale.unlink()
    _write(out_dir / "listing.json", json.dumps(main_data, ensure_ascii=False, indent=1))
    for index, frame in enumerate(frame_datas, start=1):
        _write(out_dir / f"frame_{index:02d}.json", json.dumps(frame, ensure_ascii=False, indent=1))
    _write(out_dir / "text.txt", header + main_data["text"])
    as_pasted = main_data.get("text_as_pasted")
    if as_pasted and as_pasted != main_data["text"]:
        _write(out_dir / "text_as_pasted.txt", header + as_pasted)
    detail_text = (main_data.get("detail_text") or "").strip()
    if detail_text:
        _write(out_dir / "description.txt", detail_text)

    low, high = detail_range(site, main_data.get("markers") or [], min_top=min_top, max_top=max_top)
    candidates = [(image, False) for image in sorted(main_data["images"], key=lambda i: i["top"])]
    candidates += [(image, True) for frame in frame_datas for image in frame["images"]]

    saved = 0
    seen: set[str] = set()
    dropped: dict[str, int] = {}
    failures: list[str] = []
    for image, is_frame in candidates:
        reason = keep_image(site, image, low, high, is_frame=is_frame)
        if reason is None:
            url = normalize_image_url(site, image["src"])
            if url in seen:
                reason = "중복"
        if reason:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue
        seen.add(url)
        try:
            body, content_type = fetch(url, main_data["url"])
        except Exception as error:  # noqa: BLE001 - 한 장 실패로 상품 전체를 버리지 않는다
            failures.append(f"{url} ({error})")
            continue
        saved += 1
        (out_dir / f"img_{saved:02d}{extension_of(url, content_type)}").write_bytes(body)
        if pause:
            time.sleep(pause)
    return {"saved": saved, "dropped": dropped, "failures": failures, "range": (low, high)}


@dataclass(frozen=True)
class BatchItem:
    """일괄 처리에서 JSON 하나가 갈 폴더."""

    source: Path
    out_dir: Path


def _exported_keys(out_root: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for listing in out_root.glob("*/listing.json"):
        try:
            data = json.loads(listing.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        keys.add((data.get("site", ""), data.get("collected_at", "")))
    return keys


def _next_number(out_root: Path, prefix: str) -> int:
    numbers = [int(m.group(1)) for p in out_root.glob(f"{prefix}_*") if (m := re.fullmatch(rf"{re.escape(prefix)}_(\d+)", p.name))]
    return max(numbers, default=0) + 1


def plan_batch(json_dir: Path, out_root: Path, *, prefix: str) -> list[BatchItem]:
    """다운로드 폴더의 수집 JSON을 번호 폴더에 배정한다.

    파일 이름의 수집 시각 순으로, 이미 있는 번호 다음부터 붙인다. 같은 (사이트, 수집 시각)이
    이미 내보내져 있으면 건너뛴다 (북마클릿을 두 번 눌러 같은 JSON이 두 개 생기는 경우 포함).

    Args:
        json_dir: 북마클릿 JSON이 있는 폴더.
        out_root: 상품 폴더들의 부모 (예: tests/fixtures/_raw).
        prefix: 폴더 이름 접두어 (예: "strat" → strat_01).

    Returns:
        list[BatchItem]: 처리할 JSON과 폴더.
    """
    done = _exported_keys(out_root) if out_root.exists() else set()
    number = _next_number(out_root, prefix) if out_root.exists() else 1
    plan: list[BatchItem] = []
    for source in sorted(p for p in json_dir.iterdir() if _COLLECTED_JSON.match(p.name)):
        data = json.loads(source.read_text(encoding="utf-8"))
        key = (data.get("site", ""), data.get("collected_at", ""))
        if key in done:
            continue
        done.add(key)
        plan.append(BatchItem(source=source, out_dir=out_root / f"{prefix}_{number:02d}"))
        number += 1
    return plan


def _report(name: str, data: dict, summary: dict) -> None:
    low, high = summary["range"]
    print(f"[{name}] {data.get('title', '')[:60]}")
    print(f"  상세 구역 top {low}~{high}, 글 {len(data['text'])}자, 이미지 저장 {summary['saved']}, 거름 {summary['dropped']}")
    for failure in summary["failures"]:
        print("  실패:", failure)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("json_paths", type=Path, nargs="*", help="본문 JSON, 그 뒤에 프레임 JSON들")
    parser.add_argument("--out", type=Path, help="상품 폴더 (한 상품 모드)")
    parser.add_argument("--batch", type=Path, help="수집 JSON이 있는 폴더 (일괄 모드)")
    parser.add_argument("--out-root", type=Path, help="일괄 모드에서 상품 폴더들의 부모")
    parser.add_argument("--prefix", default="strat", help="일괄 모드 폴더 접두어 (기본 strat)")
    parser.add_argument("--min-top", type=int, default=None)
    parser.add_argument("--max-top", type=int, default=None)
    args = parser.parse_args(argv)

    if args.batch:
        if not args.out_root:
            parser.error("--batch에는 --out-root가 필요합니다.")
        plan = plan_batch(args.batch, args.out_root, prefix=args.prefix)
        if not plan:
            print("새로 내보낼 JSON이 없습니다.")
            return 0
        for item in plan:
            data = json.loads(item.source.read_text(encoding="utf-8"))
            summary = export_listing(data, [], item.out_dir, pause=PAUSE_SECONDS)
            _report(item.out_dir.name, data, summary)
        return 0

    if not args.json_paths or not args.out:
        parser.error("본문 JSON과 --out 폴더를 주거나, --batch와 --out-root를 주세요.")
    main_data = json.loads(args.json_paths[0].read_text(encoding="utf-8"))
    frames = [json.loads(p.read_text(encoding="utf-8")) for p in args.json_paths[1:]]
    summary = export_listing(main_data, frames, args.out, min_top=args.min_top, max_top=args.max_top, pause=PAUSE_SECONDS)
    _report(args.out.name, main_data, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
