import { useEffect, useReducer, useRef } from "react";
import { useNavigate } from "react-router-dom";

import Button from "@/components/common/Button";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";

import Process, { type ProcessType } from "./Process";

interface Agent {
    id: string
    title: string
    job: string
    detail: string
    status: ProcessType
}

// 제품별로 다뤄야 하는 상태(에이전트 목록 + 그중 몇 개까지 공개됐는지)를 하나로 묶어서
// products 배열 하나로만 관리한다. "인덱스 X만 바꾸기" 패턴이 여러 곳에 흩어지지 않도록 reducer로 모은다.
interface ProductState {
    agents: Agent[]
    visibleCount: number
}

interface JudgementState {
    products: ProductState[]
    selectedProduct: number
    // 실제로 진행 중인(자동 전환의 기준이 되는) 제품. 히스토리 확인을 위해 이전 탭으로 돌아가도
    // selectedProduct만 바뀌고 이 값은 그대로라, 자동 전환이 다시 튀어오르지 않는다.
    furthestProduct: number
}

type JudgementAction =
    | { type: "SELECT_PRODUCT"; index: number }
    // SSE 이벤트(또는 수동 정정)로 특정 에이전트의 상태 일부가 갱신될 때 공통으로 쓰는 액션.
    | { type: "AGENT_UPDATED"; productIndex: number; agentId: string; patch: Partial<Pick<Agent, "status" | "detail">> }
    | { type: "PRODUCT_ADVANCED" }
    // TODO: SSE 연동 시 제거. 데모 시퀀스상 다음 단계로 진행시키는 액션.
    | { type: "DEMO_TICKED"; productIndex: number };

// TODO: 백엔드 연동 전까지 쓰는 임시 목업. title/job/detail/status 전부 실제로는 백엔드(SSE)가 내려주는 값이라
// 연동 시점에 이 배열은 통째로 걷어내고, 초기 에이전트 목록도 SSE(혹은 별도 API)로 받아와야 한다.
// 에이전트가 확실히 fixed 된다면 프론트에서 하드코딩 가능성도 있다.
const MOCK_INITIAL_AGENTS: Agent[] = [
    { id: "agent-1", title: "접수관", job: "상세페이지 인식", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-2", title: "통관사", job: "관세청 확인", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-3", title: "제품 안전 전문가", job: "해당되는 법률", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-4", title: "식약 전문가", job: "식품/성분 규제", detail: "에이전트를 부를 지 결정중", status: "call" },
];

// TODO: 실제로는 업로드 단계에서 넘어온 상품 개수를 써야 한다. 아직 페이지 간 데이터 전달이 연동되지 않아 임시로 고정.
const MOCK_PRODUCT_COUNT = 3;

// TODO: SSE 연동 전까지 화면 확인용 임시 데모 데이터. 실제로는 status/detail 모두 백엔드 이벤트로 온다.
// 연동 시점에 이 시퀀스와 DEMO_TICKED 액션, 아래 시뮬레이션용 useEffect를 통째로 제거하고,
// SSE onmessage에서 AGENT_UPDATED를 dispatch하면 된다.
const DEMO_SEQUENCE: Record<string, { status: ProcessType; detail: string }[]> = {
    "agent-1": [
        { status: "call", detail: "에이전트를 부를 지 결정중" },
        { status: "act", detail: "에이전트 일하는 중" },
        { status: "end", detail: "에이전트 호출 완료" },
    ],
    "agent-2": [
        { status: "call", detail: "에이전트를 부를 지 결정중" },
        { status: "fail", detail: "에이전트 호출 실패" },
    ],
    "agent-3": [
        { status: "call", detail: "에이전트를 부를 지 결정중" },
        { status: "skip", detail: "에이전트 호출 불필요" },
    ],
    "agent-4": [
        { status: "call", detail: "에이전트를 부를 지 결정중" },
        { status: "act", detail: "에이전트 일하는 중" },
        { status: "end", detail: "에이전트 호출 완료" },
    ],
};

const TERMINAL_STATUSES: ProcessType[] = ["end", "skip", "fail"];
const ACTIVE_STATUSES: ProcessType[] = ["call", "act"];
const isProductDone = (agents: Agent[]) => agents.every((agent) => TERMINAL_STATUSES.includes(agent.status));

// 이전 에이전트가 끝나기(end/skip/fail) 전까지는 다음 블럭을 보여주지 않는다.
const getNaturalVisibleCount = (agents: Agent[]) => {
    const firstActiveIndex = agents.findIndex((agent) => ACTIVE_STATUSES.includes(agent.status));
    return firstActiveIndex === -1 ? agents.length : firstActiveIndex + 1;
};

const createInitialState = (): JudgementState => ({
    products: Array.from({ length: MOCK_PRODUCT_COUNT }, () => ({
        agents: MOCK_INITIAL_AGENTS.map((agent) => ({ ...agent })),
        visibleCount: 1,
    })),
    selectedProduct: 0,
    furthestProduct: 0,
});

function judgementReducer(state: JudgementState, action: JudgementAction): JudgementState {
    switch (action.type) {
        case "SELECT_PRODUCT":
            return { ...state, selectedProduct: action.index };

        case "AGENT_UPDATED": {
            const targetProduct = state.products[action.productIndex];
            const updatedAgents = targetProduct.agents.map((agent) =>
                agent.id === action.agentId ? { ...agent, ...action.patch } : agent,
            );
            // 한 번 공개된 에이전트는 이후 "정정"으로 이전 에이전트가 되살아나도 다시 숨겨지지 않도록,
            // 지금까지 공개된 개수와 자연 진행 개수 중 큰 값만 반영한다(렌더링 중 별도 setState 불필요).
            const updatedProduct: ProductState = {
                agents: updatedAgents,
                visibleCount: Math.max(targetProduct.visibleCount, getNaturalVisibleCount(updatedAgents)),
            };
            return {
                ...state,
                products: state.products.map((product, index) => (index === action.productIndex ? updatedProduct : product)),
            };
        }

        case "PRODUCT_ADVANCED":
            return {
                ...state,
                furthestProduct: state.furthestProduct + 1,
                selectedProduct: state.furthestProduct + 1,
            };

        case "DEMO_TICKED": {
            const activeAgent = state.products[action.productIndex].agents.find((agent) =>
                ACTIVE_STATUSES.includes(agent.status),
            );
            if (!activeAgent) {
                return state;
            }

            const sequence = DEMO_SEQUENCE[activeAgent.id];
            const currentStep = sequence.findIndex((step) => step.status === activeAgent.status);
            const nextStep = sequence[currentStep + 1];
            if (!nextStep) {
                return state;
            }

            return judgementReducer(state, {
                type: "AGENT_UPDATED",
                productIndex: action.productIndex,
                agentId: activeAgent.id,
                patch: nextStep,
            });
        }

        default:
            return state;
    }
}

function JudgementPage() {
    const [state, dispatch] = useReducer(judgementReducer, undefined, createInitialState);
    const { products, selectedProduct, furthestProduct } = state;
    const navigate = useNavigate();

    const currentProduct = products[selectedProduct];
    const visibleAgents = currentProduct.agents.slice(0, currentProduct.visibleCount);
    const allProductsDone = products.every((product) => isProductDone(product.agents));

    // 새 프로세스가 나타나거나 다른 제품 탭으로 전환될 때, 그 시점의 마지막(현재 단계) 프로세스로 자동 스크롤한다.
    const currentAgentRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        currentAgentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, [selectedProduct, visibleAgents.length]);

    // TODO: SSE 연동 시 제거. 현재 선택된 제품을 1.5초마다 데모 시퀀스상 다음 단계로 진행시킨다.
    useEffect(() => {
        const interval = setInterval(() => {
            dispatch({ type: "DEMO_TICKED", productIndex: selectedProduct });
        }, 1500);

        return () => clearInterval(interval);
    }, [selectedProduct]);

    // 현재 진행 중인 제품 판정이 끝나면 자동으로 다음 제품 탭으로 넘어가서 판정을 다시 시작한다.
    // 히스토리 확인을 위해 이전 탭을 보고 있는 동안(selectedProduct !== furthestProduct)에는 동작하지 않는다.
    useEffect(() => {
        if (selectedProduct !== furthestProduct) {
            return;
        }

        if (!isProductDone(currentProduct.agents) || furthestProduct >= products.length - 1) {
            return;
        }

        const timeout = setTimeout(() => {
            dispatch({ type: "PRODUCT_ADVANCED" });
        }, 1500);
        return () => clearTimeout(timeout);
    }, [currentProduct.agents, selectedProduct, furthestProduct, products.length]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품을 확인하고 있습니다." description="네 명의 전문가가 각자 맡은 법령을 확인합니다."/>

            <ProductTabs
                count={products.length}
                selected={selectedProduct}
                onSelect={(index) => dispatch({ type: "SELECT_PRODUCT", index })}
            />

            <div className="flex flex-col gap-4">
                {visibleAgents.map((agent, index) => (
                    <div key={agent.id} ref={index === visibleAgents.length - 1 ? currentAgentRef : undefined}>
                        <Process
                            type={agent.status}
                            title={agent.title}
                            job={agent.job}
                            detail={agent.detail}
                            onCorrect={
                                agent.status === "skip" || agent.status === "fail"
                                    ? () =>
                                        dispatch({
                                            type: "AGENT_UPDATED",
                                            productIndex: selectedProduct,
                                            agentId: agent.id,
                                            patch: { status: "act" },
                                        })
                                    : undefined
                            }
                        />
                    </div>
                ))}
            </div>

            {allProductsDone && (
                <div className="flex w-full justify-end">
                    <Button text="확인이 필요한 질문 →" onClick={() => navigate("/question")} fontSize={15} />
                </div>
            )}
        </div>
    );
}

export default JudgementPage;
