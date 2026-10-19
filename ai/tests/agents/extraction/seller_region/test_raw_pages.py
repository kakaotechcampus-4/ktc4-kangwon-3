"""로컬에 받은 상세페이지 원문으로 쇼핑몰 화면이 바뀌었는지 확인한다.

원문은 저장소에 없어서(tests/fixtures/README.md) CI에서는 건너뛴다. 새 페이지를 모아
tests/fixtures/_raw에 넣고 돌리면, 알아본 쇼핑몰인데 표지를 못 찾은 페이지가 실패로 나온다.
로그 경고는 놓치기 쉬워서 테스트로 확인한다(멘토 리뷰).
"""

from pathlib import Path

import pytest

from app.agents.extraction.seller_region import extract_seller_region

RAW_FILES = sorted((Path(__file__).parents[3] / "fixtures" / "_raw").glob("*.txt"))

pytestmark = pytest.mark.skipif(not RAW_FILES, reason="로컬 원문(tests/fixtures/_raw)이 없습니다.")


@pytest.mark.parametrize("path", RAW_FILES, ids=lambda path: path.stem)
def test_알아본_쇼핑몰_페이지는_판매자_구역과_제목을_찾는다(path: Path):
    region = extract_seller_region(path.read_text(encoding="utf-8"))

    if region.site is None:
        pytest.skip("지원하지 않는 쇼핑몰이거나 일부만 붙여 넣은 입력")
    assert region.trimmed, f"{region.site} 화면 표지를 찾지 못했습니다. 화면 구조가 바뀌었는지 확인하세요."
    assert region.title, f"{region.site} 판매자 제목을 찾지 못했습니다."
