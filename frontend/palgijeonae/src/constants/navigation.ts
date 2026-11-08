export interface NavItem {
    label: string
    to: string
}

// 헤더 메뉴바에 노출하는 주요 페이지
export const NAV_ITEMS: NavItem[] = [
    { label: "메인", to: "/" },
    { label: "상품 진단", to: "/upload" },
];
