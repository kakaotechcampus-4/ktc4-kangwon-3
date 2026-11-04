import agentChildren from "@/assets/main-agentChildren.svg";
import agentCustoms from "@/assets/main-agentCustoms.svg";
import agentElectrical from "@/assets/main-agentElectrical.svg";
import agentFoodDrug from "@/assets/main-agentFoodDrug.svg";
import agentLabelAd from "@/assets/main-agentLabelAd.svg";
import agentRadio from "@/assets/main-agentRadio.svg";

export interface AgentDomainInfo {
    key: string
    icon: string
    name: string
    description: string
}

export const AGENT_DOMAINS: AgentDomainInfo[] = [
    {
        key: "children",
        icon: agentChildren,
        name: "어린이제품",
        description: "어린이가 쓰는 제품인지 확인하고, KC 안전인증과 표시 의무를 지켰는지 짚어요.",
    },
    {
        key: "customs",
        icon: agentCustoms,
        name: "관세",
        description: "구매대행·사입 특성상 생기는 통관·관세 이슈와 수입 요건을 확인해요.",
    },
    {
        key: "electrical",
        icon: agentElectrical,
        name: "전기용품",
        description: "전기로 작동하는 제품이면 전기용품 안전관리법상 KC 인증 대상인지 확인해요.",
    },
    {
        key: "foodDrug",
        icon: agentFoodDrug,
        name: "식품·의약품",
        description: "먹거나 바르는 제품이면 식품·화장품·의료기기 관련 신고·인증 의무를 확인해요.",
    },
    {
        key: "labelAd",
        icon: agentLabelAd,
        name: "표시·광고",
        description: "상세페이지 문구가 과장·허위 광고에 해당하지 않는지, 필수 표시사항이 빠지지 않았는지 봐요.",
    },
    {
        key: "radio",
        icon: agentRadio,
        name: "전파·통신기기",
        description: "무선 기능이 있는 제품이면 전파법상 적합성평가(KC) 대상인지 확인해요.",
    },
];
