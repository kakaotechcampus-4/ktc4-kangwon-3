import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import apiClient from '@/api/client'
import logoutIcon from '@/assets/header-logout.png'
import logo from '@/assets/logo.png'
import { useAuthStore } from '@/store/useAuthStore'

function Header() {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isAuthReady = useAuthStore((state) => state.isAuthReady)
    const logout = useAuthStore((state) => state.logout)
    const navigate = useNavigate()

    const logoutMutation = useMutation({
        mutationFn: () => apiClient.post('/api/v1/auth/logout'),
        // 서버 요청 성공 여부와 무관하게 액세스 토큰은 즉시 메모리에서 제거
        onSettled: () => {
            logout()
            navigate('/')
        },
    })

    const handleLogoClick = () => {
        navigate('/')
    }

    const handleButtonClick = () => {
        navigate(isLoggedIn ? '/mypage' : '/login')
    }

    return (
        <header className="fixed top-0 left-0 z-50 flex w-full items-center justify-between border-b border-neutral-border bg-white px-5 py-4">
            <img src={logo}
                alt="Logo"
                className="cursor-pointer w-[150px] object-contain"
                onClick={handleLogoClick} />
            <div className="flex items-center gap-3">
                {isAuthReady && (
                    <>
                        <button
                            className="flex cursor-pointer items-center justify-center rounded-full border border-neutral-border px-8 py-2 text-base font-medium text-neutral-dark"
                            onClick={handleButtonClick}
                        >
                            {isLoggedIn ? '마이페이지' : '로그인'}
                        </button>
                        {isLoggedIn && (
                            <button
                                className="flex cursor-pointer items-center justify-center"
                                onClick={() => logoutMutation.mutate()}
                            >
                                <img
                                    src={logoutIcon}
                                    alt="Logout"
                                    className="h-7 w-7"
                                />
                            </button>
                        )}
                    </>
                )}
            </div>
        </header>
    );
}

export default Header;
