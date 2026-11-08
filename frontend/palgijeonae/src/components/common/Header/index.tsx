import { useMutation } from '@tanstack/react-query'
import { useId, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'

import apiClient from '@/api/core/client'
import logo from '@/assets/logo.png'
import MobileMenu from '@/components/common/MobileMenu'
import ProfileMenu from '@/components/common/ProfileMenu'
import { NAV_ITEMS } from '@/constants/navigation'
import { useIsMobile } from '@/hooks/useIsMobile'
import { cn } from '@/lib/cn'
import { useAuthStore } from '@/store/useAuthStore'

function Header() {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isAuthReady = useAuthStore((state) => state.isAuthReady)
    const logout = useAuthStore((state) => state.logout)
    const navigate = useNavigate()
    const { pathname } = useLocation()
    const isMobile = useIsMobile()

    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const [menuPathname, setMenuPathname] = useState(pathname)
    const menuId = useId()
    const menuButtonRef = useRef<HTMLButtonElement>(null)

    // 이동하면 메뉴를 닫는다. 화면이 데스크톱 폭으로 넓어졌을 때도 닫아서, 다시 좁아졌을 때 저절로 열려 있지 않게 한다.
    if (menuPathname !== pathname) {
        setMenuPathname(pathname)
        setIsMenuOpen(false)
    }
    if (!isMobile && isMenuOpen) {
        setIsMenuOpen(false)
    }

    const logoutMutation = useMutation({
        mutationFn: () => apiClient.post('/api/v1/auth/logout'),
        // 서버 요청 성공 여부와 무관하게 액세스 토큰은 즉시 메모리에서 제거
        onSettled: () => {
            logout()
            navigate('/')
        },
    })

    return (
        <header className="fixed top-0 left-0 z-50 h-14.25 w-full border-b border-neutral-line bg-white md:h-16">
            <div className="mx-auto flex h-full w-full max-w-400 items-center justify-between px-5 md:px-10 lg:px-18">
                <div className="flex h-full items-center gap-10">
                    <Link to="/">
                        <img src={logo}
                            alt="사이트 로고"
                            className="h-8 w-24 object-contain md:h-10 md:w-30" />
                    </Link>
                    <nav className="hidden h-full items-center gap-7 md:flex">
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
                <div className="hidden items-center gap-3 md:flex">
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
                <button
                    ref={menuButtonRef}
                    type="button"
                    aria-label={isMenuOpen ? '메뉴 닫기' : '메뉴 열기'}
                    aria-expanded={isMenuOpen}
                    aria-controls={isMenuOpen ? menuId : undefined}
                    onClick={() => setIsMenuOpen((prev) => !prev)}
                    className="flex size-9 cursor-pointer items-center justify-center rounded-lg text-neutral-text outline-none focus-visible:ring-3 focus-visible:ring-primary/25 md:hidden"
                >
                    <svg aria-hidden viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        {isMenuOpen ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
                    </svg>
                </button>
            </div>
            {isMenuOpen && (
                <MobileMenu
                    id={menuId}
                    onClose={() => setIsMenuOpen(false)}
                    onLogout={() => logoutMutation.mutate()}
                    returnFocusRef={menuButtonRef}
                />
            )}
        </header>
    );
}

export default Header;
