"""세로로 긴 캡처 이미지를 겹치는 정사각형 조각으로 잘라 추출에 넘긴다 (#462).

모델은 이미지를 정해진 크기 안으로 줄여서 보므로, 세로로 긴 캡처를 통째로 넣으면 글자가 뭉개져 작은 글자를 놓치고
원문에 없는 값을 낸다(#323, #371 실측). 가로폭 크기 정사각형으로 겹치게 자르면 경계에서 잘린 줄이 다른 조각에
온전히 남고, 조각을 순서대로 한 호출에 넣어 문맥도 이어진다. 조건(정사각형·20% 겹침)은 #371 실측과 같음.
"""

import base64
import binascii
import io
import logging
from collections.abc import Callable

import httpx
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# 세로가 가로의 이 배수를 넘을 때만 자름. 일반 상품 사진(1:1·3:4)은 그대로, 폰 화면 캡처(약 2.2배)부터 자름
SPLIT_RATIO = 1.5
# 조각끼리 겹치는 비율 (#371 실측 조건)
OVERLAP = 0.2
# 상품당 조각 수 상한. 실측에서 조각만큼 입력 토큰이 늘어(약 2.4배) FE 이미지 장수 상한(20장)과 맞춤
MAX_TILES = 20
# JPEG 품질. PNG는 조각 20개면 요청이 수십 MB가 됨
JPEG_QUALITY = 90
# 이미지 받기 상한. FE·BE 업로드 상한(10MB)과 같음
FETCH_TIMEOUT_SECONDS = 10.0
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def split_tall_image(data: bytes) -> list[bytes] | None:
    """세로로 긴 이미지를 가로폭 크기 정사각형 조각(JPEG)으로 위에서부터 겹치게 자른다.

    Args:
        data: 이미지 파일 바이트.

    Returns:
        list[bytes] | None: 조각 JPEG 바이트(위에서부터 순서대로). 자를 만큼 길지 않으면 None.

    Raises:
        UnidentifiedImageError: 이미지로 읽을 수 없는 경우.
    """
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
        if height <= width * SPLIT_RATIO:
            return None
        rgb = image.convert("RGB")
    step = max(1, round(width * (1 - OVERLAP)))
    # 마지막 조각은 바닥에 맞춤. 앞 조각과 더 많이 겹쳐도 아래쪽 글자가 잘리지 않게
    tops = list(range(0, height - width, step)) + [height - width]
    tiles = []
    for top in tops:
        buffer = io.BytesIO()
        rgb.crop((0, top, width, top + width)).save(buffer, format="JPEG", quality=JPEG_QUALITY)
        tiles.append(buffer.getvalue())
    return tiles


def _fetch(url: str) -> bytes:
    """이미지 주소에서 바이트를 받는다. 상한을 넘으면 실패."""
    with httpx.stream("GET", url, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes():
            data += chunk
            if len(data) > MAX_IMAGE_BYTES:
                raise ValueError(f"이미지가 {MAX_IMAGE_BYTES}바이트를 넘습니다: {url}")
    return bytes(data)


class ImageSplitter:
    """추출 입력의 이미지 주소 중 세로로 긴 이미지만 조각 data URI로 바꾼다.

    이미지를 받거나 읽지 못하면 원래 주소를 그대로 둠 (모델 쪽이 직접 받을 수 있어 진단을 실패로 끝내지 않음).

    Args:
        fetch: 주소 → 이미지 바이트. 테스트에서 가짜를 넣을 때 주입.
        max_tiles: 상품당 조각 수 상한. 넘는 긴 이미지는 자르지 않고 원래 주소로 둠.
    """

    def __init__(self, fetch: Callable[[str], bytes] | None = None, *, max_tiles: int = MAX_TILES) -> None:
        self._fetch = fetch or _fetch
        self._max_tiles = max_tiles

    def prepare(self, image_urls: list[str]) -> list[str]:
        """긴 이미지만 조각으로 바꾼 이미지 주소 목록을 만든다. 순서는 원래 순서, 조각은 위에서부터.

        Args:
            image_urls: http(s) 주소 또는 data URI.

        Returns:
            list[str]: 짧은 이미지는 원래 주소, 긴 이미지는 조각 data URI.
        """
        prepared: list[str] = []
        tile_count = 0
        for url in image_urls:
            tiles = self._tiles(url)
            if tiles is None:
                prepared.append(url)
            elif tile_count + len(tiles) > self._max_tiles:
                logger.warning("조각 수 상한(%d)을 넘어 긴 이미지를 자르지 않고 넘김 (조각 %d개)", self._max_tiles, len(tiles))
                prepared.append(url)
            else:
                tile_count += len(tiles)
                prepared += ["data:image/jpeg;base64," + base64.b64encode(tile).decode() for tile in tiles]
        if tile_count:
            logger.info("긴 이미지를 조각으로 나눔 (이미지 %d장 → %d장, 조각 %d개)",
                        len(image_urls), len(prepared), tile_count)
        return prepared

    def _tiles(self, url: str) -> list[bytes] | None:
        """이미지의 조각. 짧은 이미지거나 받기·읽기에 실패하면 None."""
        try:
            data = _decode_data_uri(url) if url.startswith("data:") else self._fetch(url)
            return split_tall_image(data)
        except (httpx.HTTPError, ValueError, binascii.Error, UnidentifiedImageError, OSError) as exc:
            logger.warning("이미지를 읽지 못해 원래 주소로 넘김: %s (%s)", url[:80], type(exc).__name__)
            return None


def _decode_data_uri(url: str) -> bytes:
    """data URI(base64)의 바이트."""
    header, _, payload = url.partition(",")
    if ";base64" not in header:
        raise ValueError("base64가 아닌 data URI입니다.")
    return base64.b64decode(payload, validate=True)
