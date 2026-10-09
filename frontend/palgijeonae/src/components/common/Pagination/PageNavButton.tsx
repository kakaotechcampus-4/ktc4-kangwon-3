import lastPageIcon from "@/assets/mypage-last-page.svg";
import nextPageIcon from "@/assets/mypage-next-page.svg";
import { cn } from "@/lib/cn";

type PageNavButtonType = "first" | "prev" | "next" | "last";

interface PageNavButtonInfo {
    icon: string
    alt: string
    flip?: boolean
}

// 버튼 종류별 아이콘/라벨/좌우 반전 여부. "이전"은 "다음" 아이콘을 좌우 반전해서 재사용한다.
const PAGE_NAV_BUTTON_INFO: Record<PageNavButtonType, PageNavButtonInfo> = {
    first: { icon: lastPageIcon, alt: "처음", flip: true },
    prev: { icon: nextPageIcon, alt: "이전", flip: true },
    next: { icon: nextPageIcon, alt: "다음" },
    last: { icon: lastPageIcon, alt: "마지막 페이지" },
};

interface PageNavButtonProps {
    type: PageNavButtonType
    disabled: boolean
    onClick: () => void
}

// 처음/이전/다음/마지막 페이지 이동 버튼 공통 마크업
function PageNavButton({ type, disabled, onClick }: PageNavButtonProps) {
    const { icon, alt, flip } = PAGE_NAV_BUTTON_INFO[type];

    return (
        <button type="button" disabled={disabled} onClick={onClick} className="cursor-pointer disabled:cursor-default disabled:opacity-30">
            <img src={icon} alt={alt} className={cn("h-4 w-4", flip && "-scale-x-100")} />
        </button>
    );
}

export default PageNavButton;
