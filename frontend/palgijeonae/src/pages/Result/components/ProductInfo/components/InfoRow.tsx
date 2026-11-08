import type { ReactNode } from "react";

interface InfoRowProps {
    label: string
    children: ReactNode
}

// 라벨 + 내용 한 줄. 내용 쪽 마크업만 호출부마다 다르게 둔다.
function InfoRow({ label, children }: InfoRowProps) {
    return (
        <div className="flex w-full flex-col gap-1 md:flex-row md:items-start md:gap-5">
            <h3 className="shrink-0 text-[13px] font-bold text-neutral-muted md:w-30 md:text-base">{label}</h3>
            {children}
        </div>
    );
}

export default InfoRow;
