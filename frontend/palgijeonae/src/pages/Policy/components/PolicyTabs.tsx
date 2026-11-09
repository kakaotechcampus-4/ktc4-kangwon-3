import { NavLink } from "react-router-dom";

import { POLICY_LINKS, type PolicyType } from "@/constants/navigation.ts";
import { cn } from "@/lib/cn.ts";

const POLICY_TYPES = Object.keys(POLICY_LINKS) as PolicyType[];

// 두 문서를 오가는 탭. 헤더 메뉴에는 정책 페이지가 없어서 푸터 링크와 이 탭으로만 이동한다.
function PolicyTabs() {
    return (
        <nav aria-label="정책 문서" className="flex gap-5 border-b border-neutral-line md:gap-7">
            {POLICY_TYPES.map((type) => (
                <NavLink
                    key={type}
                    to={POLICY_LINKS[type].to}
                    className={({ isActive }) =>
                        cn(
                            "-mb-px border-b-2 pt-1 pb-2.5 text-[15px] whitespace-nowrap md:text-base",
                            isActive ? "border-primary font-bold text-primary" : "border-transparent font-medium text-neutral-border",
                        )
                    }
                >
                    {POLICY_LINKS[type].label}
                </NavLink>
            ))}
        </nav>
    );
}

export default PolicyTabs;
