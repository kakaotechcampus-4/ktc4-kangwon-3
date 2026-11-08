import { useSyncExternalStore } from "react";

// Tailwind의 md(768px) 미만. CSS의 `md:` 분기와 같은 기준을 JS에서 써야 할 때(말줄임 길이 등) 사용한다.
const MOBILE_MEDIA_QUERY = "(max-width: 767px)";

function subscribe(onChange: () => void) {
    const mediaQuery = window.matchMedia(MOBILE_MEDIA_QUERY);
    mediaQuery.addEventListener("change", onChange);
    return () => mediaQuery.removeEventListener("change", onChange);
}

function getSnapshot() {
    return window.matchMedia(MOBILE_MEDIA_QUERY).matches;
}

export function useIsMobile() {
    return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
