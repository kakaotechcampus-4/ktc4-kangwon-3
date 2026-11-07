import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/cn'
import { useMyInfo } from '@/pages/Mypage/hooks/useMyInfo'

interface ProfileMenuProps {
    onLogout: () => void
}

const MENU_ITEM_CLASS = 'flex w-full cursor-pointer items-center px-4 py-2.5 text-left text-sm font-medium hover:bg-button-hover-bg'

/** 로그인한 회원의 프로필 칩과 드롭다운 메뉴(계정 정보, 마이페이지, 로그아웃). */
function ProfileMenu({ onLogout }: ProfileMenuProps) {
    const [isOpen, setIsOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)
    const chipRef = useRef<HTMLButtonElement>(null)
    const { data: userInfo, isPending } = useMyInfo()

    // 열려 있는 동안만 바깥 클릭과 Esc를 감지한다.
    useEffect(() => {
        if (!isOpen) return

        const handleMouseDown = (event: MouseEvent) => {
            if (!containerRef.current?.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setIsOpen(false)
                chipRef.current?.focus()
            }
        }

        document.addEventListener('mousedown', handleMouseDown)
        document.addEventListener('keydown', handleKeyDown)
        return () => {
            document.removeEventListener('mousedown', handleMouseDown)
            document.removeEventListener('keydown', handleKeyDown)
        }
    }, [isOpen])

    // 내 정보를 불러오는 동안은 이름 자리를 비워 둔 칩 모양만 보여준다.
    if (isPending) {
        return <div aria-hidden className="h-7.5 w-32.5 animate-pulse rounded-full bg-neutral-line" />
    }

    const name = userInfo?.name ?? '회원'
    const initial = Array.from(name)[0]

    const close = () => setIsOpen(false)

    return (
        <div ref={containerRef} className="relative">
            <button
                ref={chipRef}
                type="button"
                aria-haspopup="menu"
                aria-expanded={isOpen}
                onClick={() => setIsOpen((prev) => !prev)}
                className="flex h-7.5 cursor-pointer items-center gap-2 rounded-full border border-neutral-line py-1 pr-2.5 pl-1"
            >
                <span className="grid size-5.5 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-bold text-primary">
                    {initial}
                </span>
                <span className="max-w-24 truncate text-sm font-medium text-neutral-text">{name} 님</span>
                <svg
                    aria-hidden
                    viewBox="0 0 16 16"
                    className={cn('size-4 shrink-0 text-neutral-dark transition-transform duration-150', isOpen && 'rotate-180')}
                >
                    <path d="M4.5 6.5 8 10l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </button>
            {isOpen && (
                <div
                    role="menu"
                    className="absolute top-full right-0 mt-2 w-50 overflow-hidden rounded-xl border border-box-line bg-white shadow-box"
                >
                    {userInfo && (
                        <div className="flex flex-col gap-0.5 border-b border-neutral-line px-4 py-3">
                            <p className="truncate text-sm font-bold text-black">{userInfo.name}</p>
                            <p className="truncate text-xs text-neutral-muted">{userInfo.email ?? '표시할 이메일이 없어요'}</p>
                        </div>
                    )}
                    <Link to="/mypage" role="menuitem" onClick={close} className={cn(MENU_ITEM_CLASS, 'text-neutral-text')}>
                        마이페이지
                    </Link>
                    <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                            close()
                            onLogout()
                        }}
                        className={cn(MENU_ITEM_CLASS, 'text-status-danger')}
                    >
                        로그아웃
                    </button>
                </div>
            )}
        </div>
    )
}

export default ProfileMenu
