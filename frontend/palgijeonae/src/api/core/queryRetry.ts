import axios from 'axios'

const MAX_RETRY_COUNT = 3

// 429 응답의 Retry-After(초). 없거나 올바르지 않으면 null
function getRetryAfterSeconds(error: unknown): number | null {
    if (!axios.isAxiosError(error) || error.response?.status !== 429) {
        return null
    }
    const seconds = Number(error.response.headers['retry-after'])
    return seconds > 0 ? seconds : null
}

// 4xx는 다시 보내도 결과가 같아서 재시도하지 않는다. 네트워크 오류와 5xx만 최대 3회까지 재시도한다.
// 예외로 429는 서버가 Retry-After로 알려 준 시간만큼 기다렸다가 재시도한다. (Retry-After가 없으면 재시도하지 않는다)
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
    if (failureCount >= MAX_RETRY_COUNT) {
        return false
    }
    if (axios.isAxiosError(error) && error.response?.status === 429) {
        return getRetryAfterSeconds(error) !== null
    }
    const status = axios.isAxiosError(error) ? error.response?.status : undefined
    return !(status && status >= 400 && status < 500)
}

// 429는 Retry-After만큼, 그 외에는 TanStack Query 기본 백오프(1s → 2s → 4s ... 최대 30s)로 기다린다.
export function getRetryDelay(failureCount: number, error: unknown): number {
    const retryAfter = getRetryAfterSeconds(error)
    if (retryAfter !== null) {
        return retryAfter * 1000
    }
    return Math.min(1000 * 2 ** failureCount, 30_000)
}
