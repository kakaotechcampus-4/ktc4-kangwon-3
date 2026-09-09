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
                const reissueResponse = await axios.post(
                    `${API_URL}/api/v1/auth/reissue`,
                    null,
                    { withCredentials: true }
                )
                useAuthStore.getState().login(reissueResponse.data.data.accessToken)

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
