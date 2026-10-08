// 제품명 길이 제한(보이는 글자 수/grapheme 기준). 입력 중 실시간으로 자르는 기준이자 사용자에게 보여주는 숫자.
export const MAX_PRODUCT_NAME_LENGTH = 100;

// 백엔드 제한(코드 유닛 기준). 입력 중 실시간으로 자르지 않고 제출 시점에 검증하는 기준.
export const MAX_PRODUCT_NAME_CODE_UNIT_LENGTH = 200;

// 상세페이지 이미지 장수 제한
export const MAX_PRODUCT_IMAGE_COUNT = 20;

// 이미지 파일 하나당 크기 제한
export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
// 안내 메시지용(MB 단위). 바이트 값이 바뀌면 메시지도 같이 바뀌도록 여기서 파생시킨다.
export const MAX_FILE_SIZE_MB = MAX_FILE_SIZE_BYTES / (1024 * 1024);

// 파일 형식 제한
export const ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"];
// 안내 메시지용("jpeg, jpg, png, webp"). 허용 목록이 바뀌면 메시지도 같이 바뀌도록 여기서 파생시킨다.
export const ALLOWED_IMAGE_EXTENSIONS_LABEL = ALLOWED_IMAGE_MIME_TYPES.map((type) => type.replace("image/", "")).join(", ");
