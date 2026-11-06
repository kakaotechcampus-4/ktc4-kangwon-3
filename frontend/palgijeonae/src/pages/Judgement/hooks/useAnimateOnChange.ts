import { useEffect, useRef } from "react";

// OS/브라우저의 "동작 줄이기" 설정이 켜져 있는지 확인한다. 
export const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** trigger가 바뀔 때마다 ref 요소에 애니메이션을 한 번 재생한다. trigger가 0이면(첫 렌더) 재생하지 않는다. */
export function useAnimateOnChange<T extends HTMLElement>(
    trigger: number,
    keyframes: Keyframe[],
    options: KeyframeAnimationOptions,
) {
    const ref = useRef<T>(null);

    useEffect(() => {
        if (trigger === 0 || prefersReducedMotion()) return;
        const animation = ref.current?.animate(keyframes, options);
        return () => animation?.cancel();
    }, [trigger, keyframes, options]);

    return ref;
}
