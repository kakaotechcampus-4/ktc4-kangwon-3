import { useMutation } from '@tanstack/react-query'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import apiClient from '@/api/core/client'
import logo from '@/assets/logo.png'
import ProfileMenu from '@/components/common/ProfileMenu'
import { NAV_ITEMS } from '@/constants/navigation'
import { cn } from '@/lib/cn'
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

    return (
        <header className="fixed top-0 left-0 z-50 h-16 w-full border-b border-neutral-line bg-white">
            <div className="mx-auto flex h-full w-full max-w-400 items-center justify-between px-5 md:px-10 lg:px-18">
                <div className="flex h-full items-center gap-10">
                    <Link to="/">
                        <img src={logo}
                            alt="사이트 로고"
                            className="h-10 w-30 object-contain" />
                    </Link>
                    <nav className="flex h-full items-center gap-7">
                        {NAV_ITEMS.map(({ label, to }) => (
                            <NavLink
                                key={to}
                                to={to}
                                // 메인(/)은 하위 경로까지 활성으로 잡히지 않도록 정확히 일치할 때만 활성
                                end={to === '/'}
                                className={({ isActive }) =>
                                    cn(
                                        'flex h-full items-center border-b-2 text-base leading-1.5',
                                        isActive
                                            ? 'border-primary font-bold text-primary'
                                            : 'border-transparent font-medium text-neutral-text',
                                    )
                                }
                            >
                                {label}
                            </NavLink>
                        ))}
                    </nav>
                </div>
                <div className="flex items-center gap-3">
                    {isAuthReady && (
                        isLoggedIn ? (
                            <ProfileMenu onLogout={() => logoutMutation.mutate()} />
                        ) : (
                            <button
                                type="button"
                                className="flex h-7.5 cursor-pointer items-center justify-center rounded-full border border-neutral-line px-3.5 py-1 text-sm font-medium text-neutral-text"
                                onClick={() => navigate('/login')}
                            >
                                로그인
                            </button>
                        )
                    )}
                </div>
            </div>
        </header>
    );
}

export default Header;
