import { useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Button from "@/components/common/Button";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";
import { isMissingDiagnosesId } from "@/lib/routeParams";

import Process from "./Process";
import { useJudgementProcess } from "./useJudgementProcess";

// TODO: SSE 연동(api/judgement.ts) 시 diagnosesId를 useJudgementProcess에 넘겨 실제 데이터로 교체한다.
function JudgementPage() {
    const { productNames, selectedProduct, visibleAgents, isCurrentProductDone, allProductsDone, selectProduct, correctAgent } =
        useJudgementProcess();
    const { diagnosesId } = useParams<{ diagnosesId?: string }>();
    const navigate = useNavigate();

    // diagnosesId 없이 잘못 진입한 경우(예: /judgement/undefined) 업로드 페이지로 되돌린다.
    useEffect(() => {
        if (isMissingDiagnosesId(diagnosesId)) {
            alert("잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.");
            navigate("/upload", { replace: true });
        }
    }, [diagnosesId, navigate]);

    const handleQuestionsClick = () => {
        if (isMissingDiagnosesId(diagnosesId)) {
            return;
        }
        navigate(`/question/${diagnosesId}`);
    };

    // 새 프로세스가 나타나거나 다른 제품 탭으로 전환될 때 자동 스크롤한다.
    // 판정이 끝난 제품(히스토리 확인)이면 첫 프로세스로, 아직 진행 중이면 마지막(현재 단계) 프로세스로 포커싱한다.
    const focusedAgentIndex = isCurrentProductDone ? 0 : visibleAgents.length - 1;
    const focusedAgentRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        focusedAgentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, [selectedProduct, visibleAgents.length, focusedAgentIndex]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품을 확인하고 있습니다." description="네 명의 전문가가 각자 맡은 법령을 확인합니다."/>

            <ProductTabs productNames={productNames} selected={selectedProduct} onSelect={selectProduct} />

            <div className="flex flex-col gap-4">
                {visibleAgents.map((agent, index) => (
                    <Process
                        key={agent.id}
                        ref={index === focusedAgentIndex ? focusedAgentRef : undefined}
                        type={agent.status}
                        title={agent.title}
                        job={agent.job}
                        detail={agent.detail}
                        onCorrect={() => correctAgent(agent.id)}
                    />
                ))}
            </div>

            {allProductsDone && (
                <div className="flex w-full justify-end">
                    <Button text="확인이 필요한 질문 →" onClick={handleQuestionsClick} fontSize={15} />
                </div>
            )}
        </div>
    );
}

export default JudgementPage;
