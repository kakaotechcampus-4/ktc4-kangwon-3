"""입력 가드가 판단 모델(Jev)에 넣을 이미지를 만든다.

Jev는 base64 PNG·JPEG data URI만 받고, 긴 변이 1536px을 넘으면 400 (11-04 실측, 긴 캡처 통째도 400).
긴 캡처는 추출과 같은 규칙으로 정사각형 조각으로 자르고, 모든 조각·이미지를 긴 변 MAX_SIDE 이하 JPEG로 바꿈.
추출 에이전트에는 원래 주소를 그대로 넘기므로 여기서 만든 data URI는 가드에서만 씀.
"""

import base64
import binascii
import io
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from PIL import Image, UnidentifiedImageError

from ...pipeline.image_split import JPEG_QUALITY, _decode_data_uri, _fetch, split_tall_image

logger = logging.getLogger(__name__)

# 긴 변 상한. Jev 상한(1536px)보다 작게 줄여 토큰을 아낌 (면적에 비례: 800px 약 2천, 1536px 약 6.4천)
MAX_SIDE = 1024
# 상품당 판단 이미지(조각 포함) 상한. 넘는 이미지는 보지 않고 넘김 (fail-open)
MAX_IMAGES = 60
# 받기·읽기 실패로 보는 예외. 픽셀 수가 Pillow 상한을 넘는 이미지(DecompressionBombError)는 Exception을 바로 상속
_READ_ERRORS = (httpx.HTTPError, ValueError, binascii.Error, UnidentifiedImageError, OSError,
                Image.DecompressionBombError)


@dataclass(frozen=True)
class JudgeImages:
    """판단 모델에 넣을 이미지.

    Attributes:
        images: JPEG data URI. 원래 순서, 긴 이미지 조각은 위에서부터.
        skipped: 받기·읽기에 실패했거나 상한을 넘어 전부 또는 일부를 못 본 원래 이미지 수.
    """

    images: list[str]
    skipped: int


def prepare_judge_images(
    image_urls: list[str], *, fetch: Callable[[str], bytes] | None = None, max_images: int = MAX_IMAGES,
) -> JudgeImages:
    """이미지 주소들을 판단 모델에 넣을 JPEG data URI 목록으로 바꾼다.

    Args:
        image_urls: http(s) 주소 또는 data URI.
        fetch: 주소 → 이미지 바이트. None이면 추출과 같은 받기(크기·시간 상한 포함). 테스트에서 가짜를 넣을 때 주입.
        max_images: 판단 이미지(조각 포함) 상한.

    Returns:
        JudgeImages: 판단 이미지와 못 본 원래 이미지 수.
    """
    fetch = fetch or _fetch
    images: list[str] = []
    skipped = 0
    for url in image_urls:
        try:
            pieces = _pieces(_decode_data_uri(url) if url.startswith("data:") else fetch(url))
        except _READ_ERRORS as exc:
            logger.warning("가드 이미지를 읽지 못해 넘김: %s (%s)", url[:80], type(exc).__name__)
            skipped += 1
            continue
        room = max_images - len(images)
        if len(pieces) > room:
            logger.warning("가드 이미지 상한(%d)을 넘어 일부만 봄 (조각 %d개 중 %d개)", max_images, len(pieces), room)
            skipped += 1
        images += [_data_uri(piece) for piece in pieces[:room]]
    return JudgeImages(images=images, skipped=skipped)


def _pieces(data: bytes) -> list[bytes]:
    """이미지 하나를 긴 변 MAX_SIDE 이하 JPEG들로 바꾼다. 긴 캡처는 조각, 아니면 한 장."""
    tiles = split_tall_image(data) or [data]
    return [_shrink_jpeg(tile) for tile in tiles]


def _shrink_jpeg(data: bytes) -> bytes:
    """긴 변 MAX_SIDE 이하 RGB JPEG. 작은 이미지는 크기 그대로 형식만 바꿈 (webp·png·투명 배경 포함)."""
    with Image.open(io.BytesIO(data)) as image:
        rgb = image.convert("RGB")
    rgb.thumbnail((MAX_SIDE, MAX_SIDE))
    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def _data_uri(jpeg: bytes) -> str:
    """JPEG 바이트의 data URI."""
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
