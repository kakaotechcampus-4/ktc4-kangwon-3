import { useEffect, useRef } from "react";

import { cn } from "@/lib/cn";

interface CheckboxProps {
    checked: boolean
    // 일부만 선택된 상태. checked보다 먼저 보여준다.
    indeterminate?: boolean
    disabled?: boolean
    onChange: (checked: boolean) => void
    ariaLabel: string
    className?: string
}

function Checkbox({ checked, indeterminate = false, disabled, onChange, ariaLabel, className }: CheckboxProps) {
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.indeterminate = indeterminate;
        }
    }, [indeterminate]);

    return (
        // 보이는 크기(20px)는 그대로 두고, 라벨을 44px로 키운 뒤 음수 마진으로 레이아웃 크기만 되돌려 터치 영역을 넓힌다.
        <label className={cn("relative -m-3 flex size-11 shrink-0 cursor-pointer items-center justify-center", disabled && "cursor-default", className)}>
            <input
                ref={inputRef}
                type="checkbox"
                checked={checked}
                disabled={disabled}
                aria-label={ariaLabel}
                onChange={(event) => onChange(event.target.checked)}
                className="peer size-5 cursor-[inherit] appearance-none rounded-[5px] border-[1.5px] border-field-line bg-white outline-none checked:border-primary checked:bg-primary indeterminate:border-primary indeterminate:bg-primary focus-visible:ring-3 focus-visible:ring-primary/25 disabled:border-box-line disabled:bg-button-disabled-bg"
            />
            <svg
                aria-hidden="true"
                viewBox="0 0 20 20"
                fill="none"
                className="pointer-events-none absolute size-5 text-white peer-disabled:text-button-disabled-text"
            >
                {indeterminate ? (
                    <path d="M5.5 10h9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                ) : checked ? (
                    <path d="M5 10.5l3.2 3.2L15 6.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                ) : null}
            </svg>
        </label>
    );
}

export default Checkbox;
