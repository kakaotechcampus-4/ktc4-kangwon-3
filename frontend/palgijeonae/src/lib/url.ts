const HTTP_URL_PATTERN = /^https?:\/\//i;

/**
 * 사용자가 입력한 문자열이 http(s)://로 시작하는 URL인지 검증하는 유틸 함수.
 * javascript: 같은 다른 스킴이나 /mypage 같은 앱 내부 라우팅 경로로 이동하지 않도록 http(s)로 제한할 때 쓴다.
 */
export function isHttpUrl(value: string): boolean {
    return HTTP_URL_PATTERN.test(value);
}
