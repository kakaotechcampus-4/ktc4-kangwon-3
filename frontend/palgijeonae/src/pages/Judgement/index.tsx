import { useEffect, useState } from "react";

import Process, { type ProcessType } from "./Process";
import SectionIntro from "../../components/common/SectionIntro";

interface Agent {
    id: string
    title: string
    job: string
    detail: string
    status: ProcessType
}

// TODO: 백엔드 연동 전까지 쓰는 임시 목업. title/job/detail/status 전부 실제로는 백엔드(SSE)가 내려주는 값이라
// 연동 시점에 이 배열은 통째로 걷어내고, 초기 에이전트 목록도 SSE(혹은 별도 API)로 받아와야 한다.
// 에이전트가 확실히 fixed 된다면 프론트에서 하드코딩 가능성도 있다.
const MOCK_INITIAL_AGENTS: Agent[] = [
    { id: "agent-1", title: "접수관", job: "상세페이지 인식", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-2", title: "통관사", job: "관세청 확인", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-3", title: "제품 안전 전문가", job: "해당되는 법률", detail: "에이전트를 부를 지 결정중", status: "call" },
    { id: "agent-4", title: "식약 전문가", job: "식품/성분 규제", detail: "에이전트를 부를 지 결정중", status: "call" },
];

// TODO: SSE 연동 전까지 화면 확인용 임시 데모 데이터. 실제로는 status/detail 모두 백엔드 이벤트로 온다.
// 연동 시점에 이 시퀀스와 아래 useEffect(진행 시뮬레이션)를 통째로 제거하고, SSE onmessage에서 updateAgent를 호출한다.
const DEMO_SEQUENCE: Record<string, { status: ProcessType; detail: string }[]> = {
    "agent-1": [
        { status: "call", detail: "에이전트를 부를 지 결정중" },
        { status: "act", detail: "에이전트 일하는 중" },
        { status: "end", detail: "에이전트 호출 완료" },
    ],
    "agent-2": [
        { status: "call", detail: "에이전트를 부를 지 결정중" },
        { status: "act", detail: "에이전트 일하는 중" },
        { status: "end", detail: "에이전트 호출 완료" },
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

function JudgementPage() {
    const [agents, setAgents] = useState<Agent[]>(MOCK_INITIAL_AGENTS);

    // 이전 에이전트가 끝나기(end/skip) 전까지는 다음 블럭을 보여주지 않는다.
    // 추후 SSE로 status 업데이트가 들어오면 이 파생 로직만으로 다음 블럭이 자연스럽게 드러난다.
    const firstActiveIndex = agents.findIndex((agent) => agent.status === "call" || agent.status === "act");
    const visibleAgents = firstActiveIndex === -1 ? agents : agents.slice(0, firstActiveIndex + 1);

    // SSE 이벤트로 {id, status, detail}이 함께 오는 걸 그대로 넘길 수 있도록 status 외 필드도 부분 갱신 가능하게 둔다.
    const updateAgent = (id: string, patch: Partial<Pick<Agent, "status" | "detail">>) => {
        setAgents((prev) => prev.map((agent) => (agent.id === id ? { ...agent, ...patch } : agent)));
    };

    // TODO: SSE 연동 시 제거. 현재 활성 에이전트를 1.5초마다 데모 시퀀스상 다음 단계로 진행시킨다.
    useEffect(() => {
        const interval = setInterval(() => {
            setAgents((prev) => {
                const activeIndex = prev.findIndex((agent) => agent.status === "call" || agent.status === "act");
                if (activeIndex === -1) {
                    clearInterval(interval);
                    return prev;
                }

                const active = prev[activeIndex];
                const sequence = DEMO_SEQUENCE[active.id];
                const currentStep = sequence.findIndex((step) => step.status === active.status);
                const nextStep = sequence[currentStep + 1];
                if (!nextStep) {
                    return prev;
                }

                return prev.map((agent) => (agent.id === active.id ? { ...agent, ...nextStep } : agent));
            });
        }, 1500);

        return () => clearInterval(interval);
    }, []);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품을 확인하고 있습니다." description="네 명의 전문가가 각자 맡은 법령을 확인합니다."/>

            <div className="flex flex-col gap-4">
                {visibleAgents.map((agent) => (
                    <Process
                        key={agent.id}
                        type={agent.status}
                        title={agent.title}
                        job={agent.job}
                        detail={agent.detail}
                        onCorrect={agent.status === "skip" ? () => updateAgent(agent.id, { status: "act" }) : undefined}
                    />
                ))}
            </div>
        </div>
    );
}

export default JudgementPage;
