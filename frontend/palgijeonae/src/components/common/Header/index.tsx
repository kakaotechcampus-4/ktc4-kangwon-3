import { useNavigate } from 'react-router-dom'

import apiClient from '../../../api/client'
import { useAuthStore } from '../../../store/useAuthStore'
import logo from '../../../assets/logo.png'
import logoutIcon from '../../../assets/header-logout.png'

function Header() {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const logout = useAuthStore((state) => state.logout)
    const navigate = useNavigate()

    const handleLogoClick = () => {
        navigate('/')
    }

    const handleButtonClick = () => {
        navigate(isLoggedIn ? '/mypage' : '/login')
    }

    const handleLogoutClick = async () => {
        try {
            await apiClient.post('/api/v1/auth/logout')
        } finally {
            // 서버 요청 성공 여부와 무관하게 액세스 토큰은 즉시 메모리에서 제거
            logout()
            navigate('/')
        }
    }

    return (
        <header className="fixed top-0 left-0 z-50 flex w-full items-center justify-between border-b border-neutral-border bg-white px-5 py-4">
            <img src={logo}
                alt="Logo"
                className="cursor-pointer w-[150px] object-contain"
                onClick={handleLogoClick} />
            <div className="flex items-center gap-3">
                <button
                    className="flex cursor-pointer items-center justify-center rounded-full border border-neutral-border px-8 py-2 text-base font-medium text-neutral-dark"
                    onClick={handleButtonClick}
                >
                    {isLoggedIn ? '마이페이지' : '로그인'}
                </button>
                {isLoggedIn && (
                    <button
                        className="flex cursor-pointer items-center justify-center"
                        onClick={handleLogoutClick}
                    >
                        <img
                            src={logoutIcon}
                            alt="Logout"
                            className="h-7 w-7"
                        />
                    </button>
                )}
            </div>
        </header>
    );
}

export default Header;
