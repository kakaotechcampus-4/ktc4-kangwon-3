import { ToolName } from "@/api/product";
import agentChildren from "@/assets/main-agentChildren.svg";
import agentCustoms from "@/assets/main-agentCustoms.svg";
import agentElectrical from "@/assets/main-agentElectrical.svg";
import agentFoodDrug from "@/assets/main-agentFoodDrug.svg";
import agentLabelAd from "@/assets/main-agentLabelAd.svg";
import agentRadio from "@/assets/main-agentRadio.svg";

export interface AgentDomainInfo {
    toolName: ToolName
    icon: string
    name: string
    role: string
    description: string
    chips: string[]
    // 통관만 모든 상품에 항상 적용되는 검토라 별도 태그를 붙인다.
    alwaysCheckTag?: string
}

export const AGENT_DOMAINS: AgentDomainInfo[] = [
    {
        toolName: ToolName.Customs,
        icon: agentCustoms,
        name: "통관 에이전트",
        role: "모든 상품을 가장 먼저 확인해요",
        description: "상품 정보로 HS코드 후보를 찾아요.\n수입신고 때 세관장확인 요건이 붙는지 확인해요.\n국내 판매용 KC 인증과는 따로 봐요.",
        chips: ["HS코드 후보", "세관장확인 요건", "수입신고 서류"],
        alwaysCheckTag: "항상 확인",
    },
    {
        toolName: ToolName.Children,
        icon: agentChildren,
        name: "어린이 제품 에이전트",
        role: "어린이가 쓰는 상품인지 확인해요",
        description: "만 13세 이하 대상 표기, 완구·학용품·유아용품인지 봐요.\n해당하면 어린이제품 안전 특별법상 필요한\n인증·확인 절차를 정리해요.",
        chips: ["만 13세 이하 대상 표기", "완구·학용품·유아용품"],
    },
    {
        toolName: ToolName.Electrical,
        icon: agentElectrical,
        name: "전기 안전 에이전트",
        role: "전기와 배터리를 확인해요",
        description: "전기로 작동하거나 배터리가 든 상품, 발열 기능을 봐요.\n전기용품 및 생활용품 안전관리법상\n안전인증·안전확인 대상인지 확인해요.",
        chips: ["전기로 작동", "배터리 내장", "보조배터리·건전지", "발열 기능"],
    },
    {
        toolName: ToolName.Radio,
        icon: agentRadio,
        name: "전파 에이전트",
        role: "무선 기능을 확인해요",
        description: "블루투스·Wi-Fi·무선충전 같은 무선 기능을 봐요.\n적합성평가 대상이면 사입 전 KC 전파인증이 필요해요.\n구매대행은 개인 사용 면제 범위를 함께 알려드려요.",
        chips: ["블루투스·Wi-Fi·RF 리모컨", "무선충전", "RFID 차단·전자파 차폐"],
    },
    {
        toolName: ToolName.FoodDrug,
        icon: agentFoodDrug,
        name: "식품·의약품 에이전트",
        role: "먹거나 몸에 닿는 상품을 확인해요",
        description: "음식에 닿거나 피부·점막에 쓰는 상품인지 봐요.\n치료·미용 효과를 내세우는 문구도 확인해요.\n식품용 기구·화장품·의료기기 해당 여부를 정리해요.",
        chips: ["음식에 닿는 식기·용기", "피부·점막에 쓰는 상품", "치료·미용 효과 표방"],
    },
    {
        toolName: ToolName.LabelAd,
        icon: agentLabelAd,
        name: "표시·광고 에이전트",
        role: "판매 문구를 확인해요",
        description: "효능, '100% 차단' 같은 최상급 표현,\n'FDA 승인' 같은 인증 문구를 찾아요.\n그대로 쓰면 문제가 될 수 있는 문구를 짚어 드려요.",
        chips: ["효능·효과 표방", "최상급·절대 표현", "인증·승인 문구", "과장 수치", "안전 단정"],
    },
];
