import type { ReactNode } from "react";
import { useEffect } from "react";

interface BottomActionBarProps {
    // 왼쪽 영역. 진행 상황 요약을 담는다.
    children: ReactNode
    // 오른쪽 영역. 주요 버튼을 담는다.
    actions: ReactNode
    // true이면 바를 숨긴다. 화면 아래 여백(--action-bar-space)은 그대로 둬서 숨겨도 본문이 움직이지 않는다.
    hidden?: boolean
}

/** 화면 아래에 고정된 바. 왼쪽에는 진행 상황 요약, 오른쪽에는 주요 버튼을 보여준다. */
function BottomActionBar({ children, actions, hidden = false }: BottomActionBarProps) {
    // 바가 화면 아래를 덮는 만큼 페이지 맨 아래(푸터)가 가려지지 않도록, Layout이 읽는 여백 값을 정한다.
    useEffect(() => {
        document.documentElement.style.setProperty("--action-bar-space", "calc(5rem + env(safe-area-inset-bottom))");
        return () => {
            document.documentElement.style.removeProperty("--action-bar-space");
        };
    }, []);

    return (
        <div hidden={hidden} className="fixed inset-x-0 bottom-0 z-40 border-t border-neutral-line bg-white pb-[env(safe-area-inset-bottom)]">
            {/* 안쪽 폭은 Layout의 main 폭과 같게 맞춘다. */}
            <div className="mx-auto flex w-full max-w-297 items-center justify-between gap-3 px-5 py-3 md:w-3/5 md:min-w-150 md:px-0 md:py-4">
                <div className="flex min-w-0 items-center gap-3">{children}</div>
                <div className="flex shrink-0 items-center gap-2">{actions}</div>
            </div>
        </div>
    );
}

export default BottomActionBar;
