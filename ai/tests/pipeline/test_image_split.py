"""긴 캡처 이미지를 겹치는 정사각형 조각으로 자르는지, 추출 입력의 이미지 주소를 어떻게 바꾸는지 확인한다 (#462)."""

import base64
import io

import httpx
import pytest
from PIL import Image

from app.pipeline.image_split import ImageSplitter, split_tall_image

TALL_URL = "https://img.example/tall.png"
SHORT_URL = "https://img.example/short.png"


def _png(width: int, height: int, bands: list[tuple[int, int, int]] | None = None) -> bytes:
    """세로 띠 색으로 칠한 PNG. 띠마다 높이가 같음."""
    image = Image.new("RGB", (width, height), (255, 255, 255))
    if bands:
        band = height // len(bands)
        for index, color in enumerate(bands):
            image.paste(color, (0, index * band, width, (index + 1) * band if index < len(bands) - 1 else height))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _decode(data_uri: str) -> Image.Image:
    assert data_uri.startswith("data:image/jpeg;base64,")
    return Image.open(io.BytesIO(base64.b64decode(data_uri.split(",", 1)[1])))


def _data_uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


def test_세로가_가로의_1_5배_이하면_자르지_않는다():
    assert split_tall_image(_png(100, 150)) is None


def test_긴_이미지는_가로폭_정사각형으로_20퍼센트_겹치게_위에서부터_자른다():
    # 100x400: 위치 0, 80, 160, 240 + 마지막은 바닥에 맞춰 300
    tiles = split_tall_image(_png(100, 400, bands=[(255, 0, 0), (0, 0, 255)]))

    images = [Image.open(io.BytesIO(tile)) for tile in tiles]
    assert [image.size for image in images] == [(100, 100)] * 5
    # 첫 조각은 위쪽 빨강, 마지막 조각은 아래쪽 파랑
    red, _, blue_first = images[0].convert("RGB").getpixel((50, 50))
    assert red > 200 and blue_first < 60
    red_last, _, blue = images[-1].convert("RGB").getpixel((50, 50))
    assert blue > 200 and red_last < 60


def test_짧은_이미지_주소는_그대로_두고_긴_이미지만_조각으로_바꾼다():
    pages = {TALL_URL: _png(100, 400), SHORT_URL: _png(100, 100)}
    splitter = ImageSplitter(fetch=pages.__getitem__)

    urls = splitter.prepare([SHORT_URL, TALL_URL, SHORT_URL])

    assert urls[0] == SHORT_URL and urls[-1] == SHORT_URL
    assert len(urls) == 7
    assert all(_decode(url).size == (100, 100) for url in urls[1:6])


def test_data_URI로_온_긴_이미지도_자른다():
    splitter = ImageSplitter(fetch=lambda url: pytest.fail("data URI는 받지 않아야 함"))

    urls = splitter.prepare([_data_uri(_png(100, 400))])

    assert len(urls) == 5


@pytest.mark.parametrize("fetch", [
    lambda url: (_ for _ in ()).throw(httpx.ConnectError("연결 실패")),
    lambda url: b"not an image",
])
def test_이미지를_받거나_읽지_못하면_원래_주소를_그대로_둔다(fetch):
    # 모델 쪽이 직접 받을 수 있으니 실패로 끝내지 않음
    assert ImageSplitter(fetch=fetch).prepare([TALL_URL]) == [TALL_URL]


def test_조각_수_상한을_넘는_긴_이미지는_자르지_않고_원래_주소로_둔다():
    other = "https://img.example/tall-2.png"
    pages = {TALL_URL: _png(100, 400), other: _png(100, 400)}
    splitter = ImageSplitter(fetch=pages.__getitem__, max_tiles=6)

    urls = splitter.prepare([TALL_URL, other])

    # 첫 이미지 5조각, 두 번째는 5조각을 더하면 상한(6)을 넘어 원래 주소
    assert len(urls) == 6 and urls[-1] == other
