import { useEffect, useState } from "react";

import type { ProcessType } from "./Process";
import { isActiveStatus, isTerminalStatus } from "./processStatus";

export interface Agent {
    id: string
    title: string
    job: string
    detail: string
    status: ProcessType
}

// 에이전트 목록 + 공개된(이미 확정된) 개수를 제품 단위로 묶은 상태.
interface ProductState {
    agents: Agent[]
    visibleCount: number
}

interface JudgementState {
    products: ProductState[]
    selectedProduct: number
    // 자동 전환의 기준이 되는, 실제 진행 중인 제품.
    furthestProduct: number
}

// TODO: 백엔드(SSE) 연동 전 임시 목업. 연동 시 이 배열과 초기 에이전트 목록 로직을 교체한다.
const MOCK_INITIAL_AGENTS: Agent[] = [
    { id: "agent-1", title: "접수관", job: "상세페이지 인식", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-2", title: "통관사", job: "관세청 확인", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-3", title: "제품 안전 전문가", job: "해당되는 법률", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-4", title: "식약 전문가", job: "식품/성분 규제", detail: "에이전트를 부를 지 결정중", status: "call" },
];

// TODO: 실제로는 업로드 단계에서 넘어온 상품 개수를 써야 한다. 아직 페이지 간 데이터 전달이 연동되지 않아 임시로 고정.
const MOCK_PRODUCT_COUNT = 3;

// TODO: SSE 연동 전 임시 데모 데이터. 연동 시 이 시퀀스, tickDemo, 데모용 useEffect를 제거하고
// SSE onmessage에서 updateAgent를 호출한다.
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

// TODO: SSE 연동 시 제거. 
// 데모 시퀀스가 다음 단계로 넘어가는 주기.
const DEMO_TICK_INTERVAL_MS = 3000;
// 제품 판정 완료 후 다음 탭으로 자동 전환되기까지의 지연.
const PRODUCT_ADVANCE_DELAY_MS = 500;

const isProductDone = (agents: Agent[]) => agents.every((agent) => isTerminalStatus(agent.status));

// 진행 중인 에이전트의 다음 블럭은 아직 보여주지 않는다.
const getNaturalVisibleCount = (agents: Agent[]) => {
    const firstActiveIndex = agents.findIndex((agent) => isActiveStatus(agent.status));
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

// 에이전트 상태 일부를 갱신한다.
const updateAgent = (
    state: JudgementState,
    productIndex: number,
    agentId: string,
    patch: Partial<Pick<Agent, "status" | "detail">>,
): JudgementState => {
    const targetProduct = state.products[productIndex];
    const updatedAgents = targetProduct.agents.map((agent) =>
        agent.id === agentId ? { ...agent, ...patch } : agent,
    );
    // 공개된 에이전트는 정정으로 다시 숨겨지지 않도록 최대값을 유지한다.
    const updatedProduct: ProductState = {
        agents: updatedAgents,
        visibleCount: Math.max(targetProduct.visibleCount, getNaturalVisibleCount(updatedAgents)),
    };
    return {
        ...state,
        products: state.products.map((product, index) => (index === productIndex ? updatedProduct : product)),
    };
};

const advanceProduct = (state: JudgementState): JudgementState => ({
    ...state,
    furthestProduct: state.furthestProduct + 1,
    selectedProduct: state.furthestProduct + 1,
});

// TODO: SSE 연동 시 제거. 데모 시퀀스를 한 단계 진행시킨다.
const tickDemo = (state: JudgementState, productIndex: number): JudgementState => {
    const activeAgent = state.products[productIndex].agents.find((agent) => isActiveStatus(agent.status));
    if (!activeAgent) {
        return state;
    }

    const sequence = DEMO_SEQUENCE[activeAgent.id];
    const currentStep = sequence.findIndex((step) => step.status === activeAgent.status);
    const nextStep = sequence[currentStep + 1];
    if (!nextStep) {
        return state;
    }

    return updateAgent(state, productIndex, activeAgent.id, nextStep);
};

// 판정 페이지의 상태와 부수효과를 전담하는 훅.
export function useJudgementProcess() {
    const [state, setState] = useState<JudgementState>(createInitialState);
    const { products, selectedProduct, furthestProduct } = state;

    const currentProduct = products[selectedProduct];
    const visibleAgents = currentProduct.agents.slice(0, currentProduct.visibleCount);
    const isCurrentProductDone = isProductDone(currentProduct.agents);
    const allProductsDone = products.every((product) => isProductDone(product.agents));

    // TODO: SSE 연동 시 제거. 선택된 제품의 데모를 주기적으로 진행시킨다.
    useEffect(() => {
        const interval = setInterval(() => {
            setState((prev) => tickDemo(prev, selectedProduct));
        }, DEMO_TICK_INTERVAL_MS);

        return () => clearInterval(interval);
    }, [selectedProduct]);

    // 판정이 끝나면 다음 제품 탭으로 자동 전환한다. 이전 탭을 보는 동안에는 동작하지 않는다.
    useEffect(() => {
        if (selectedProduct !== furthestProduct) {
            return;
        }

        if (!isProductDone(currentProduct.agents) || furthestProduct >= products.length - 1) {
            return;
        }

        const timeout = setTimeout(() => {
            setState(advanceProduct);
        }, PRODUCT_ADVANCE_DELAY_MS);
        return () => clearTimeout(timeout);
    }, [currentProduct.agents, selectedProduct, furthestProduct, products.length]);

    return {
        productCount: products.length,
        selectedProduct,
        visibleAgents,
        isCurrentProductDone,
        allProductsDone,
        selectProduct: (index: number) => setState((prev) => ({ ...prev, selectedProduct: index })),
        correctAgent: (agentId: string) =>
            setState((prev) => updateAgent(prev, selectedProduct, agentId, { status: "act" })),
    };
}
