export interface NavItem {
    label: string
    to: string
}

// 헤더 메뉴바에 노출하는 주요 페이지
export const NAV_ITEMS: NavItem[] = [
    { label: "메인", to: "/" },
    { label: "상품 진단", to: "/upload" },
];

export type PolicyType = "terms" | "privacy";

// 정책 문서 링크. /docs는 nginx가 AI 서버로 보내는 경로라서 /policy를 쓴다.
export const POLICY_LINKS: Record<PolicyType, NavItem> = {
    terms: { label: "이용약관", to: "/policy/terms" },
    privacy: { label: "개인정보처리방침", to: "/policy/privacy" },
};

export const CONTACT_EMAIL = "admin@palgijeone.com";
export const GITHUB_URL = "https://github.com/kakaotechcampus-4/ktc4-kangwon-3";
