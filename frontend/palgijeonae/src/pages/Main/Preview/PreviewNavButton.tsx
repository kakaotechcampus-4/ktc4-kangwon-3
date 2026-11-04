import nextIcon from "@/assets/mypage-next-page.svg";
import { cn } from "@/lib/cn";

interface PreviewNavButtonProps {
    direction: "prev" | "next"
    onClick: () => void
}

/** 캐러셀 이전/다음 버튼. 40px 원형. "이전"은 기존 "다음" 아이콘을 좌우 반전해서 재사용한다. */
function PreviewNavButton({ direction, onClick }: PreviewNavButtonProps) {
    const isNext = direction === "next";

    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={isNext ? "다음 화면" : "이전 화면"}
            className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-neutral-border bg-white"
        >
            <img src={nextIcon} alt="" className={cn("h-5 w-5", !isNext && "-scale-x-100")} />
        </button>
    );
}

export default PreviewNavButton;
