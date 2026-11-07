import * as Sentry from '@sentry/react'
import axios, { AxiosError } from 'axios'

import { useAuthStore } from '@/store/useAuthStore'

import { classifyApiError, toPathTemplate } from './sentryErrorPolicy'

const API_URL = import.meta.env.VITE_API_URL

// 응답이 이 시간 안에 오지 않으면 요청을 끊고 실패로 처리한다.
const REQUEST_TIMEOUT_MS = 10_000

const apiClient = axios.create({
    baseURL: API_URL,
    withCredentials: true,
    timeout: REQUEST_TIMEOUT_MS,
})

apiClient.interceptors.request.use((config) => {
    const { accessToken } = useAuthStore.getState()
    if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
})

// 리프레시 토큰이 재발급마다 회전되기 때문에, 동시에 여러 요청이 401을 받아도
// reissue는 한 번만 호출하고 나머지는 그 결과를 공유해서 재시도해야 함
let refreshPromise: Promise<string> | null = null

export const reissueAccessToken = () => {
    if (!refreshPromise) {
        refreshPromise = axios
            // apiClient를 거치지 않으므로 타임아웃을 따로 건다.
            .post(`${API_URL}/api/v1/auth/reissue`, null, { withCredentials: true, timeout: REQUEST_TIMEOUT_MS })
            .then((response) => {
                const accessToken = response.data.data.accessToken
                useAuthStore.getState().login(accessToken)
                return accessToken
            })
            .finally(() => {
                refreshPromise = null
            })
    }
    return refreshPromise
}

apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const { config, response } = error

        // 이미 재시도한 요청이면 더 시도하지 않고 그대로 실패 처리
        if (response?.status !== 401 || config._retried) {
            throw error
        }

        if (response.data?.code === 'AUTH-001') {
            // 액세스 토큰 만료: reissue로 새 토큰 받아서 원 요청 1회만 재시도
            try {
                await reissueAccessToken()
                config._retried = true
                return apiClient(config)
            } catch {
                // reissue 자체가 실패(AUTH-003 등) → 재로그인 유도
            }
        }

        useAuthStore.getState().logout()
        window.location.href = '/login'
        throw error
    }
)

// 전송 여부·레벨 판단은 상태코드가 아닌 BE 에러 코드 기준(sentryErrorPolicy)으로 한다.
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (axios.isCancel(error)) {
            throw error
        }

        const status = error.response?.status
        const code = error.response?.data?.code
        // 타임아웃은 응답이 없어 상태코드로 구분되지 않으므로 error 대신 warning으로 보낸다.
        const level = !error.response && isTimeoutError(error)
            ? 'warning'
            : classifyApiError({ status, code, retried: Boolean(error.config?._retried) })

        if (level) {
            const method = error.config?.method?.toUpperCase() ?? 'UNKNOWN'
            const path = toPathTemplate(error.config?.url ?? '')

            // 이슈 제목(에러 타입)은 그대로 두고, 설명만 사용자에게 보여주는 것과 같은 한글 메시지로 바꾼다.
            error.message = getErrorMessage(error, error.message)

            Sentry.withScope((scope) => {
                scope.setLevel(level)
                scope.setFingerprint([method, path, code ?? 'UNKNOWN'])
                scope.setContext('api_error', { method, url: path, status, code })
                Sentry.captureException(error)
            })
        }

        throw error
    }
)

interface ApiErrorResponse {
    code?: string
    message?: string
    details?: { message: string }[]
}

// ECONNABORTED는 요청 중단("Request aborted")에도 쓰여서 메시지로 타임아웃만 골라낸다.
function isTimeoutError(error: AxiosError): boolean {
    return error.code === AxiosError.ETIMEDOUT || (error.code === AxiosError.ECONNABORTED && error.message.includes('timeout'))
}

// 백엔드 에러 응답(details[0].message 우선, 없으면 message)에서 사용자에게 보여줄 메시지를 꺼낸다.
export function getErrorMessage(error: unknown, fallback: string): string {
    if (axios.isAxiosError<ApiErrorResponse>(error)) {
        const data = error.response?.data

        if (!error.response && isTimeoutError(error)) {
            return '응답이 지연되고 있어요. 잠시 후 다시 시도해주세요.'
        }

        // 요청 한도 초과(429 COMMON-011): Retry-After 헤더(초)로 안내 문구를 만든다.
        if (data?.code === 'COMMON-011') {
            const retryAfter = Number(error.response?.headers['retry-after'])
            return retryAfter > 0 ? `${retryAfter}초 후 다시 시도해주세요.` : '잠시 후 다시 시도해주세요.'
        }

        return data?.details?.[0]?.message ?? data?.message ?? error.message
    }

    if (error instanceof Error) {
        return error.message
    }

    return fallback
}

export default apiClient
