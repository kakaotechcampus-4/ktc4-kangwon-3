import { useEffect, useState } from "react";

function isTextField(element: EventTarget | null) {
    return element instanceof HTMLTextAreaElement || element instanceof HTMLInputElement;
}

/** 글자를 입력하는 칸(input, textarea)에 포커스가 있는 동안 true. 모바일에서는 이때 화면 키보드가 올라온다. */
export function useTextFieldFocused() {
    const [focused, setFocused] = useState(() => isTextField(document.activeElement));

    useEffect(() => {
        const handleFocusIn = (event: FocusEvent) => setFocused(isTextField(event.target));
        const handleFocusOut = () => setFocused(false);
        document.addEventListener("focusin", handleFocusIn);
        document.addEventListener("focusout", handleFocusOut);
        return () => {
            document.removeEventListener("focusin", handleFocusIn);
            document.removeEventListener("focusout", handleFocusOut);
        };
    }, []);

    return focused;
}
