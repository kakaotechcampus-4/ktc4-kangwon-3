// 라우트 파라미터가 없거나, undefined/null이 문자 그대로 들어온 경우를 검증하는 유틸 함수
export function isMissingRouteParam(value: string | undefined): boolean {
    return !value || value === "undefined" || value === "null";
}