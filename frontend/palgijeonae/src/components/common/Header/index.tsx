import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'

import apiClient from '@/api/core/client'
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

    const handleButtonClick = () => {
        navigate(isLoggedIn ? '/mypage' : '/login')
    }

    return (
        <header className="fixed top-0 left-0 z-50 h-16 w-full border-b border-neutral-line bg-white">
            <div className="mx-auto flex h-full w-full max-w-400 items-center justify-between px-5 md:px-10 lg:px-18">
                <div className="flex items-center">
                    <Link to="/">
                        <img src={logo}
                            alt="사이트 로고"
                            className="h-10 w-30 object-contain" />
                    </Link>
                </div>
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
                                        alt="로그아웃"
                                        className="h-7 w-7"
                                    />
                                </button>
                            )}
                        </>
                    )}
                </div>
            </div>
        </header>
    );
}

export default Header;
