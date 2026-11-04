"""trace용으로 감싼 진단 부품: 기록 중이 아니면 원래와 같고, 기록 중이면 이미지별 자르기 결과를 남긴다."""

import io

from PIL import Image

from app.diagnosis.tracing import TracedImageSplitter
from app.observability.trace import trace_run
from app.pipeline.image_split import ImageSplitter

TALL_URL = "https://img.example/tall.png"
SHORT_URL = "https://img.example/short.png"
BROKEN_URL = "https://img.example/broken.png"


def _png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


PAGES = {TALL_URL: _png(100, 400), SHORT_URL: _png(100, 100), BROKEN_URL: b"not an image"}


def test_기록_중이_아니면_원래_이미지_자르기와_결과가_같다():
    urls = [SHORT_URL, TALL_URL]

    assert TracedImageSplitter(fetch=PAGES.__getitem__).prepare(urls) == ImageSplitter(
        fetch=PAGES.__getitem__).prepare(urls)


def test_기록_중이면_이미지마다_자름·안_자름·상한_초과와_보낸_장수를_남긴다(tmp_path):
    # 100x400은 조각 5개, 상한 6이면 두 번째 긴 이미지는 넘김
    splitter = TracedImageSplitter(fetch=PAGES.__getitem__, max_tiles=6)

    with trace_run(tmp_path) as recorder:
        prepared = splitter.prepare([SHORT_URL, TALL_URL, BROKEN_URL, TALL_URL])

    assert recorder.info["image_split"] == {
        "images": [
            {"url": SHORT_URL, "result": "not_split"},
            {"url": TALL_URL, "result": "split", "tiles": 5},
            {"url": BROKEN_URL, "result": "not_split"},
            {"url": TALL_URL, "result": "over_limit", "tiles": 5},
        ],
        "sent": len(prepared),
    }
    assert len(prepared) == 8


def test_data_URI_이미지는_본문_대신_형식만_남긴다(tmp_path):
    with trace_run(tmp_path) as recorder:
        TracedImageSplitter(fetch=PAGES.__getitem__).prepare(["data:image/png;base64,AAAA"])

    assert recorder.info["image_split"]["images"] == [{"url": "data:image/png;base64,…(생략)", "result": "not_split"}]
