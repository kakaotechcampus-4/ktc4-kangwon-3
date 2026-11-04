# 상세페이지 수집 도구 (추출 평가용)

테무·알리 상세페이지의 글과 **상세 설명 이미지**를 사람 손 캡처 없이 `_raw/` 상품 폴더로 모은다 (#567).
한 상품에 사람이 하는 일은 "페이지 열기 → 북마크 한 번 → 저장" 뿐이다.

| 파일 | 하는 일 |
|---|---|
| `collect_listing.js` | 브라우저에서 실행. 끝까지 스크롤하고 "더보기"를 펼친 뒤 글·이미지 주소·구역 표지 위치를 JSON으로 다운로드 |
| `collect_listing.bookmarklet.txt` | 위 파일을 북마크 URL에 넣을 수 있게 한 줄로 만든 것 |
| `download_listing.py` | JSON을 상품 폴더(`text.txt` + `img_NN.jpg` …)로 푼다. 상세 설명 구역 밖 이미지는 거름 |

## 1. 북마크 등록 (한 번만)

1. 크롬에서 `Ctrl + Shift + O`(북마크 관리자) → 오른쪽 위 ⋮ → **새 북마크 추가**
2. 이름은 아무거나, URL 칸에 `collect_listing.bookmarklet.txt` 내용 전체를 붙여 넣고 저장

북마크 대신 개발자도구 콘솔(`F12` → Console)에 `collect_listing.js` 내용을 붙여 넣어도 된다.
처음 한 번은 크롬이 `allow pasting`을 타이핑하라고 하는데, 그건 크롬 전체에 한 번만 하면 된다.

`collect_listing.js`를 고쳤으면 한 줄 버전을 다시 만든다:

```bash
python -c "s=open('scripts/collect/collect_listing.js',encoding='utf-8').read();open('scripts/collect/collect_listing.bookmarklet.txt','w',encoding='utf-8').write('javascript:'+' '.join(l.strip() for l in s.splitlines() if l.strip()))"
```

## 2. 상품마다

1. 상품 페이지를 연다 (로그인·지역 안내 화면이 아니라 상품 글이 보이는지 확인).
2. 북마크를 누른다. 페이지가 저절로 끝까지 내려가고 1~2분 뒤 알림이 뜨면서 `temu_<시각>.json` /
   `aliexpress_<시각>.json`이 다운로드 폴더에 떨어진다.
   - 알림의 "상세 구역 안 N장"이 0이면 구역 표지를 못 찾은 것. JSON의 `markers`·`probe`를 보고 규칙을 보완한다.
   - 크롬이 "여러 파일 다운로드" 권한을 물으면 **허용**.
3. 다음 상품으로.

## 3. 폴더로 풀기 (모은 뒤 한 번)

```bash
# ai/ 에서. 다운로드 폴더의 수집 JSON을 전부 strat_01, strat_02 … 로 (이미 내보낸 것은 건너뜀)
python scripts/collect/download_listing.py --batch ~/Downloads --out-root tests/fixtures/_raw --prefix strat

# 한 상품만. 북마클릿이 새 탭으로 연 설명 프레임에서 받은 JSON이 있으면 뒤에 붙인다
python scripts/collect/download_listing.py Downloads/temu_x.json --out tests/fixtures/_raw/strat_01
```

상품 폴더에 남는 것:

| 파일 | 내용 |
|---|---|
| `text.txt` | "더보기"를 펼친 뒤 글. 첫 줄 `# <사이트> <주소>` (기존 `_raw` 규약). 스펙표가 전부 들어 있어 정답표 기준 |
| `text_as_pasted.txt` | 펼치기 전 글. 실제 사용자가 Ctrl+A로 붙여 넣는 형태 (펼친 글과 다를 때만) |
| `description.txt` | 알리 shadow DOM 안의 설명 글. 일반 복사로는 안 딸려 온다 (있을 때만) |
| `img_NN.jpg` | 상세 설명 구역의 이미지 원본. 테무 1600px JPEG, 알리 원본 |
| `listing.json` | 북마클릿 원본 기록 (표지 위치·펼침·프레임 진단) |

### 상세 설명 이미지를 고르는 규칙

| 사이트 | 구역 | 구역 안에서도 거르는 것 |
|---|---|---|
| 테무 | "제품 세부 정보" ~ "관심 상품 둘러보기"/"인기 추천" | 연관 상품(alt가 "품목 사진"으로 시작), 배너·아바타 호스트 |
| 알리 | "개요"/"Description" ~ "구매자 질문"/"면책 조항"/"함께 볼 만한 상품" | 연관 상품(alt가 있는 480×480) |

둘 다 가로·세로 300px 미만은 뺀다. 표지를 못 찾은 JSON은 `--min-top`/`--max-top`으로 범위를 직접 준다.

## 주의

- 수집물은 판매자 저작물이다. `_raw/`는 git에서 제외돼 있고, 외부에 공개하거나 재배포하지 않는다.
- 사람 속도로만 쓴다. 페이지는 사람이 하나씩 열고, 스크립트는 열린 페이지 안에서만 돈다. 이미지 다운로드는 한 장마다 0.5초 쉰다.
- 리뷰는 근거로 쓰지 않는다 (추출 프롬프트 원칙 6). 리뷰 사진은 상세 구역 밖이라 걸러진다.
- 페이지 구조가 바뀌면 표지 문구부터 깨진다. `download_listing.py`의 `SITE_RULES`와 `collect_listing.js`의 `MARKERS`를 같이 고친다.
