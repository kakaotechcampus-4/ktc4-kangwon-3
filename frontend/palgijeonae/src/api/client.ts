import axios from 'axios'

import { useAuthStore } from '../store/useAuthStore'

const API_URL = import.meta.env.VITE_API_URL

const apiClient = axios.create({
    baseURL: API_URL,
    withCredentials: true,
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

const reissueAccessToken = () => {
    if (!refreshPromise) {
        refreshPromise = axios
            .post(`${API_URL}/api/v1/auth/reissue`, null, { withCredentials: true })
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

export default apiClient
