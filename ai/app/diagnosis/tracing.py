"""진단 부품을 trace에 남기게 감싼 것. 기록 중이 아니면 원래 부품과 똑같이 동작함.

부품 파일(pipeline/)은 고치지 않고, 조립(assembly.py)에서 감싼 부품을 넣음.
"""

from contextvars import ContextVar

from ..observability.trace import current_trace, image_link, trace_note
from ..pipeline.image_split import ImageSplitter

# prepare 한 번 동안 이미지마다 조각 수 (자르지 않으면 None). 여러 진단이 부품을 같이 써서 문맥 변수로
_tile_counts: ContextVar[list[int | None] | None] = ContextVar("image_tile_counts", default=None)


class TracedImageSplitter(ImageSplitter):
    """긴 이미지 자르기 전후를 trace에 남기는 이미지 자르기. 자르는 동작은 그대로.

    이미지마다 결과를 남김.
        - split: 조각으로 나눔 (조각 수)
        - not_split: 짧은 이미지거나 받기·읽기 실패 (둘은 구분 안 됨, 실패는 경고 로그)
        - over_limit: 길지만 상품당 조각 수 상한을 넘어 원래 주소로 넘김
    """

    def prepare(self, image_urls: list[str]) -> list[str]:
        """긴 이미지만 조각으로 바꾼 이미지 주소 목록을 만들고, 기록 중이면 이미지별 결과를 남긴다.

        Args:
            image_urls: http(s) 주소 또는 data URI.

        Returns:
            list[str]: 짧은 이미지는 원래 주소, 긴 이미지는 조각 data URI.
        """
        if current_trace() is None:
            return super().prepare(image_urls)
        counts: list[int | None] = []
        token = _tile_counts.set(counts)
        try:
            prepared = super().prepare(image_urls)
        finally:
            _tile_counts.reset(token)
        trace_note("image_split", {
            "images": _image_results(image_urls, counts, self._max_tiles),
            "sent": len(prepared),
        })
        return prepared

    def _tiles(self, url: str) -> list[bytes] | None:
        tiles = super()._tiles(url)
        counts = _tile_counts.get()
        if counts is not None:
            counts.append(None if tiles is None else len(tiles))
        return tiles


def _image_results(image_urls: list[str], counts: list[int | None], max_tiles: int) -> list[dict]:
    """이미지별 자르기 결과. 상한 판단은 ImageSplitter.prepare와 같은 순서로 셈.

    Args:
        image_urls: 원래 이미지 주소.
        counts: 이미지마다 조각 수 (자르지 않으면 None).
        max_tiles: 상품당 조각 수 상한.

    Returns:
        list[dict]: 주소·결과·조각 수.
    """
    results: list[dict] = []
    total = 0
    for url, count in zip(image_urls, counts):
        if count is None:
            results.append({"url": image_link(url), "result": "not_split"})
        elif total + count > max_tiles:
            results.append({"url": image_link(url), "result": "over_limit", "tiles": count})
        else:
            total += count
            results.append({"url": image_link(url), "result": "split", "tiles": count})
    return results
