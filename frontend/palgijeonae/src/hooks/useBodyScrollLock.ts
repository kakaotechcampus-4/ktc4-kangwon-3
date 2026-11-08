import { useEffect } from "react";

/** locked인 동안 배경(body) 스크롤을 막고, 끝나면 원래 값으로 되돌린다. */
export function useBodyScrollLock(locked: boolean) {
    useEffect(() => {
        if (!locked) return;

        const originalOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = originalOverflow;
        };
    }, [locked]);
}
