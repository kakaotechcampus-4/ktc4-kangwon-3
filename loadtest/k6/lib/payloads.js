// 진단 생성 요청 바디. S3를 쓰지 않도록 이미지 키 없이 TEXT_IMAGE(sourceText) 위주로 만든다.
// URL 등록은 sourceUrl만 저장하고 AI에 넘기므로(Mock은 열어 보지 않음) 섞어 둔다.
const NAMES = ['무선 이어폰', '아기 치발기', 'USB 멀티탭', '블루투스 스피커', '비타민 C', '어린이 킥보드', 'LED 무드등', '전동 칫솔'];

const SOURCE_TEXT = '해외 쇼핑몰 상세페이지에서 옮긴 설명입니다. 정격 전압 5V, 리튬 배터리 내장, 사용 연령 3세 이상. '
  + '본체 재질은 ABS 플라스틱이며 충전 케이블이 함께 들어 있습니다.';

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

export function productCount() {
  // 1개 50%, 2개 30%, 3개 20% (평균 약 1.7개)
  const r = Math.random();
  return r < 0.5 ? 1 : (r < 0.8 ? 2 : 3);
}

export function diagnosesBody(count = productCount()) {
  const products = [];
  for (let i = 0; i < count; i++) {
    const name = `${pick(NAMES)} ${Math.floor(Math.random() * 1000)}`;
    products.push(Math.random() < 0.7
      ? { productName: name, sourceType: 'TEXT_IMAGE', sourceText: SOURCE_TEXT }
      : { productName: name, sourceType: 'URL', sourceUrl: `https://example.com/item/${Math.floor(Math.random() * 1e6)}` });
  }
  return { products };
}

export function keyword() {
  return pick(['이어폰', '멀티탭', '킥보드', '비타민']);
}
