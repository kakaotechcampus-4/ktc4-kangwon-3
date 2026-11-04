import SectionIntro from "@/components/common/SectionIntro";

import AgentCard from "./AgentCard";
import { AGENT_DOMAINS } from "./constants";

/** 메인 페이지 "6개 분야 에이전트" 소개 섹션. 아이콘·설명을 좌우로 교차 배치한다. */
function AgentIntro() {
    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro
                title="6개 분야 전문 에이전트가 함께 확인해요"
                description="하나의 상품도 여러 법령에 걸릴 수 있어서, 분야별 에이전트가 나눠서 검토해요."
                size="2xl"
            />
            <ul className="flex flex-col gap-10">
                {AGENT_DOMAINS.map((domain, index) => (
                    <li key={domain.key}>
                        <AgentCard
                            icon={domain.icon}
                            name={domain.name}
                            description={domain.description}
                            reverse={index % 2 === 1}
                        />
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default AgentIntro;
