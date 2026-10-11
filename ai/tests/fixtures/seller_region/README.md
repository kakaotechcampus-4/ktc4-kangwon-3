# 판매자 구역 정제 뼈대 픽스처

실제 상세페이지 원문(`tests/fixtures/_raw`, 저장소에 없음)에서 쇼핑몰 화면 표지 줄만 남기고
상품 글은 `본문`·제목 자리표시로 바꾼 파일이다. 상품 글이 없어 공개 저장소에 올려도 된다.

- `expected.json`: 파일별 기대 결과(쇼핑몰, 잘림 여부, 제목 유무, 남는 줄)
- 테스트: `tests/utils/test_seller_region_structure.py`

정제 규칙을 일부러 바꿨거나 새 원문을 `_raw`에 넣었으면 다시 만든다.

```
python scripts/make_seller_region_skeletons.py   (ai/ 에서 실행)
```

스크립트는 뼈대마다 원문과 같은 결과가 나오는지 확인하고, 다르면 쓰지 않고 실패한다.
새 페이지에서 화면이 바뀌었는지는 `tests/utils/test_seller_region_raw.py`로 먼저 확인한다(원문이 있을 때만 실행).
