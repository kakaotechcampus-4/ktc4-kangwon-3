import { Navigate, Outlet } from 'react-router-dom'

import { useAuthStore } from '@/store/useAuthStore'

function ProtectedRoute() {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isAuthReady = useAuthStore((state) => state.isAuthReady)

    // 새로고침 직후에는 세션 복구(reissue)가 끝나기 전이라 isLoggedIn이 잠깐 false이므로,
    // 복구가 끝나기 전에는 리다이렉트하지 않고 기다린다.
    if (!isAuthReady) {
        return null
    }

    if (!isLoggedIn) {
        return <Navigate to="/login" replace />
    }

    return <Outlet />
}

export default ProtectedRoute
