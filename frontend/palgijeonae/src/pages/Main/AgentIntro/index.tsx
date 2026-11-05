import SectionIntro from "@/components/common/SectionIntro";

import AgentCard from "./AgentCard";
import { AGENT_DOMAINS } from "./constants";

/** 메인 페이지 "6개 분야 에이전트" 소개 섹션. 분야별 역할·설명을 좌우로 교차 배치한다. */
function AgentIntro() {
    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro
                title="6개 분야 에이전트가 나눠서 확인해요"
                description="통관은 모든 상품을 확인하고, 나머지는 상품에 해당하는 분야만 골라 확인해요."
                size="2xl"
            />
            <ul className="flex flex-col gap-5">
                {AGENT_DOMAINS.map((domain, index) => (
                    <li key={domain.toolName}>
                        <AgentCard
                            icon={domain.icon}
                            name={domain.name}
                            role={domain.role}
                            description={domain.description}
                            chips={domain.chips}
                            alwaysCheckTag={domain.alwaysCheckTag}
                            reverse={index % 2 === 1}
                        />
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default AgentIntro;
