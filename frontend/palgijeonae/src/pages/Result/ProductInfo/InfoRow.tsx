import type { ReactNode } from "react";

interface InfoRowProps {
    label: string
    children: ReactNode
}

// 라벨 + 내용 한 줄. 내용 쪽 마크업만 호출부마다 다르게 둔다.
function InfoRow({ label, children }: InfoRowProps) {
    return (
        <div className="flex w-full items-start gap-5">
            <h3 className="w-30 shrink-0 text-base font-bold text-neutral-muted">{label}</h3>
            {children}
        </div>
    );
}

export default InfoRow;
