import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

/**
 * 경로(pathname)가 바뀌면 화면을 맨 위로 올린다.
 * 뒤로·앞으로 가기(POP)는 브라우저가 스크롤 위치를 복원하게 두고, 해시·쿼리만 바뀌는 이동은 건드리지 않는다.
 */
export function useScrollToTop() {
    const { pathname } = useLocation();
    const navigationType = useNavigationType();
    const previousPathname = useRef(pathname);

    useEffect(() => {
        // 이전 값과 비교하지 않으면 navigationType만 바뀌는 해시 이동(POP → PUSH)에서도 맨 위로 올라간다.
        if (previousPathname.current === pathname) return;
        previousPathname.current = pathname;

        if (navigationType === "POP") return;
        window.scrollTo(0, 0);
    }, [pathname, navigationType]);
}
