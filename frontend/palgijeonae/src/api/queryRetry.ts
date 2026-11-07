import axios from 'axios'

const MAX_RETRY_COUNT = 3

// 4xx는 다시 보내도 결과가 같아서 재시도하지 않는다. 네트워크 오류와 5xx만 최대 3회까지 재시도한다.
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined
    if (status && status >= 400 && status < 500) {
        return false
    }
    return failureCount < MAX_RETRY_COUNT
}
