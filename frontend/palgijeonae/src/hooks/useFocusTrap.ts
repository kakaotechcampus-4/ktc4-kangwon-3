import { type RefObject, useEffect } from "react";

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * enabled인 동안 Tab 이동을 containers 안으로 가둔다.
 * containers의 요소를 순서대로 이어 하나의 목록으로 보고, 끝에서 Tab이면 처음으로, 처음에서 Shift+Tab이면 끝으로 보낸다.
 * 포커스가 목록 밖에 있으면 목록 안으로 끌어온다.
 */
export function useFocusTrap(enabled: boolean, containers: RefObject<HTMLElement | null>[]) {
    useEffect(() => {
        if (!enabled) return;

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key !== "Tab") return;

            const focusables = containers.flatMap((container) => {
                const element = container.current;
                if (!element) return [];
                return [...(element.matches(FOCUSABLE_SELECTOR) ? [element] : []), ...element.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)];
            });
            if (focusables.length === 0) return;

            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            const active = document.activeElement;

            if (!(active instanceof HTMLElement) || !focusables.includes(active)) {
                event.preventDefault();
                (event.shiftKey ? last : first).focus();
            } else if (event.shiftKey && active === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && active === last) {
                event.preventDefault();
                first.focus();
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [enabled, containers]);
}
