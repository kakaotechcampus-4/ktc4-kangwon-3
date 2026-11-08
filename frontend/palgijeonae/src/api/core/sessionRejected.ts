import axios from "axios";

// 세션 복구(reissue) 요청을 서버가 거절했는지 판단한다.
// 4xx는 쿠키 없음·만료·폐기처럼 다시 로그인해야 하는 경우다. 네트워크 오류·타임아웃·5xx는 잠시 실패한 것일 수 있어 세션이 끝났다고 보지 않는다.
export function isSessionRejectedError(error: unknown): boolean {
    if (!axios.isAxiosError(error) || !error.response) {
        return false;
    }

    const { status } = error.response;
    // 429는 요청 한도 초과라 세션과 무관하다.
    return status >= 400 && status < 500 && status !== 429;
}
