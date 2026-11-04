"""입력 가드가 이미지를 판단 모델(Jev)이 받는 JPEG data URI로 바꾸는지 확인한다."""

import base64
import io

import httpx
import pytest
from PIL import Image

from app.agents.input_guard.images import MAX_SIDE, prepare_judge_images

TALL_URL = "https://bucket.s3.ap-northeast-2.amazonaws.com/products/tall"
SHORT_URL = "https://bucket.s3.ap-northeast-2.amazonaws.com/products/short"


def _image(width: int, height: int, fmt: str = "PNG", mode: str = "RGB") -> bytes:
    image = Image.new(mode, (width, height), (200, 200, 200, 0) if mode == "RGBA" else (200, 200, 200))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def _decode(data_uri: str) -> Image.Image:
    assert data_uri.startswith("data:image/jpeg;base64,")
    image = Image.open(io.BytesIO(base64.b64decode(data_uri.split(",", 1)[1])))
    assert image.format == "JPEG"
    return image


def _data_uri(data: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def test_짧은_이미지는_한_장_긴_캡처는_조각으로_원래_순서대로_바꾼다():
    images = {SHORT_URL: _image(300, 300), TALL_URL: _image(100, 400)}

    result = prepare_judge_images([SHORT_URL, TALL_URL], fetch=images.__getitem__)

    # 짧은 이미지 1장 + 100x400 조각 5개 (추출과 같은 자르기)
    assert [_decode(uri).size for uri in result.images] == [(300, 300)] + [(100, 100)] * 5
    assert result.skipped == 0


@pytest.mark.parametrize(("fmt", "mode", "mime"), [
    ("WEBP", "RGB", "image/webp"),
    ("PNG", "RGBA", "image/png"),
], ids=["webp", "투명 배경 png"])
def test_JPEG가_아닌_이미지도_JPEG로_바꾼다(fmt, mode, mime):
    result = prepare_judge_images([_data_uri(_image(200, 200, fmt, mode), mime)])

    assert _decode(result.images[0]).mode == "RGB"


@pytest.mark.parametrize(("size", "expected"), [
    ((2000, 1500), (MAX_SIDE, 768)),
    ((3000, 500), (MAX_SIDE, 171)),
], ids=["큰 사진", "가로로 긴 배너"])
def test_긴_변이_상한을_넘으면_비율을_지켜_줄인다(size, expected):
    result = prepare_judge_images([SHORT_URL], fetch=lambda url: _image(*size))

    assert _decode(result.images[0]).size == expected


def test_긴_캡처_조각도_긴_변_상한으로_줄인다():
    result = prepare_judge_images([TALL_URL], fetch=lambda url: _image(1440, 3200))

    assert {_decode(uri).size for uri in result.images} == {(MAX_SIDE, MAX_SIDE)}


@pytest.mark.parametrize("error", [
    httpx.ConnectTimeout("timeout"),
    ValueError("이미지가 10485760바이트를 넘습니다"),
], ids=["받기 실패", "크기 상한 초과"])
def test_받지_못한_이미지는_건너뛰고_나머지는_바꾼다(error):
    def fetch(url: str) -> bytes:
        if url == TALL_URL:
            raise error
        return _image(300, 300)

    result = prepare_judge_images([TALL_URL, SHORT_URL], fetch=fetch)

    assert len(result.images) == 1
    assert result.skipped == 1


def test_이미지가_아닌_바이트도_건너뛴다():
    result = prepare_judge_images([SHORT_URL], fetch=lambda url: b"<html>not image</html>")

    assert result.images == []
    assert result.skipped == 1


def test_상한을_넘는_조각은_보지_않고_못_본_이미지로_센다():
    # 짧은 이미지 2장 + 조각 5개짜리 긴 캡처, 상한 4 → 짧은 2장 + 조각 2개
    images = {SHORT_URL: _image(300, 300), TALL_URL: _image(100, 400)}

    result = prepare_judge_images([SHORT_URL, SHORT_URL, TALL_URL], fetch=images.__getitem__, max_images=4)

    assert len(result.images) == 4
    assert result.skipped == 1
