import { useEffect } from "react";

/** enabled인 동안 Esc 키를 누르면 onEscape를 호출한다. 팝업·메뉴를 키보드로 닫을 때 쓴다. */
export function useEscapeKey(enabled: boolean, onEscape: () => void) {
    useEffect(() => {
        if (!enabled) return;

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                onEscape();
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [enabled, onEscape]);
}
