import { type RefObject, useRef } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import Button from '@/components/common/Button'
import { NAV_ITEMS } from '@/constants/navigation'
import { useBodyScrollLock } from '@/hooks/useBodyScrollLock'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { cn } from '@/lib/cn'
import { useMyInfo } from '@/pages/Mypage/hooks/useMyInfo'
import { useAuthStore } from '@/store/useAuthStore'

interface MobileMenuProps {
    id: string
    onClose: () => void
    onLogout: () => void
    // 메뉴를 여는 햄버거 버튼. Esc로 닫을 때 포커스를 돌려주고, Tab 이동 범위에도 포함한다.
    triggerRef: RefObject<HTMLElement | null>
}

const MEMBER_ITEM_CLASS = 'flex h-12 w-full cursor-pointer items-center px-5 text-left text-base font-medium'

interface MemberMenuProps {
    onClose: () => void
    onLogout: () => void
}

function MemberMenu({ onClose, onLogout }: MemberMenuProps) {
    const { data: userInfo, isPending } = useMyInfo()
    const name = userInfo?.name ?? '회원'

    return (
        <>
            {isPending ? (
                <div aria-hidden className="mx-5 my-3 h-9 animate-pulse rounded-full bg-neutral-line" />
            ) : (
                <div className="flex items-center gap-3 px-5 py-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary-soft text-base font-bold text-primary">
                        {Array.from(name)[0]}
                    </span>
                    <div className="flex min-w-0 flex-col">
                        <p className="truncate text-base font-bold text-black">{name}</p>
                        {userInfo && <p className="truncate text-sm text-neutral-muted">{userInfo.email ?? '표시할 이메일이 없어요'}</p>}
                    </div>
                </div>
            )}
            <Link to="/mypage" onClick={onClose} className={cn(MEMBER_ITEM_CLASS, 'text-neutral-text')}>
                마이페이지
            </Link>
            <button
                type="button"
                onClick={() => {
                    onClose()
                    onLogout()
                }}
                className={cn(MEMBER_ITEM_CLASS, 'text-status-danger')}
            >
                로그아웃
            </button>
        </>
    )
}

/** 모바일 헤더 아래로 펼쳐지는 메뉴 패널. 열려 있는 동안에만 렌더하며, 마운트된 동안 배경 스크롤을 잠근다. */
function MobileMenu({ id, onClose, onLogout, triggerRef }: MobileMenuProps) {
    const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isAuthReady = useAuthStore((state) => state.isAuthReady)
    const navigate = useNavigate()
    const panelRef = useRef<HTMLDivElement>(null)

    useBodyScrollLock(true)
    useEscapeKey(true, () => {
        onClose()
        triggerRef.current?.focus()
    })
    useFocusTrap(true, [triggerRef, panelRef])

    return (
        <div className="fixed inset-x-0 top-14.25 bottom-0">
            <div role="presentation" className="absolute inset-0 bg-black/40" onClick={onClose} />
            <div id={id} ref={panelRef} className="relative max-h-full overflow-y-auto border-b border-neutral-line bg-white shadow-box">
                <nav aria-label="주요 메뉴" className="flex flex-col py-2">
                    {NAV_ITEMS.map(({ label, to }) => (
                        <NavLink
                            key={to}
                            to={to}
                            end={to === '/'}
                            className={({ isActive }) =>
                                cn(
                                    'flex h-12 items-center border-l-3 px-5 text-base',
                                    isActive
                                        ? 'border-primary bg-primary/8 font-bold text-primary'
                                        : 'border-transparent font-medium text-neutral-text',
                                )
                            }
                        >
                            {label}
                        </NavLink>
                    ))}
                </nav>
                {isAuthReady && (
                    <div className="flex flex-col border-t border-neutral-line py-2">
                        {isLoggedIn ? (
                            <MemberMenu onClose={onClose} onLogout={onLogout} />
                        ) : (
                            <div className="flex flex-col px-5 py-2 [&>button]:w-full">
                                <Button text="로그인" variant="secondary" fontSize={16} onClick={() => navigate('/login')} />
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    )
}

export default MobileMenu
