import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ProcessingStatusType } from "@/api/types";
import Button from "@/components/common/Button";
import HelpTooltip from "@/components/common/HelpTooltip";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import SectionIntro from "@/components/common/SectionIntro";
import { isMissingRouteParam } from "@/lib/routeParams";

import ProductProgressCard from "./components/ProductProgressCard";
import StatusSummaryBar from "./components/StatusSummaryBar";
import { useJudgementProducts } from "./hooks/useJudgementProducts";
import { useStatusAnnouncement } from "./hooks/useStatusAnnouncement";

function JudgementPage() {
    const { diagnosesId } = useParams<{ diagnosesId?: string }>();
    const navigate = useNavigate();

    const isInvalidAccess = isMissingRouteParam(diagnosesId);

    // diagnosesId 없이 잘못 진입한 경우(예: /judgement/undefined) 업로드 페이지로 되돌린다.
    useEffect(() => {
        if (isInvalidAccess) {
            alert("잘못된 접근입니다. 진단서를 업로드한 후 다시 시도해주세요.");
            navigate("/upload", { replace: true });
        }
    }, [isInvalidAccess, navigate]);

    const { data, isPending, isError, refetch } = useJudgementProducts(diagnosesId, !isInvalidAccess);
    const isDiagnosisDone = data != null
        && (data.processingStatus === ProcessingStatusType.Completed || data.processingStatus === ProcessingStatusType.Failed);
    const announcement = useStatusAnnouncement(data?.products, isDiagnosisDone);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro
                title="상품을 진단하고 있어요"
                description={
                    data
                        ? `${data.products.length}개 상품을 동시에 확인하고 있어요. 질문이 생긴 상품은 먼저 답해주시면 바로 이어서 진행해요.`
                        : "상품을 확인하고 있어요."
                }
            />
            <p role="status" className="sr-only">{announcement}</p>
            {isPending ? (
                <LoadingSpinner />
            ) : isError ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-status-danger">진행 상황을 불러오지 못했어요.</p>
                    <button
                        type="button"
                        onClick={() => refetch()}
                        className="text-sm font-medium cursor-pointer text-neutral-border underline underline-offset-2"
                    >
                        다시 시도
                    </button>
                </div>
            ) : (
                <div className="flex w-full flex-col gap-6">
                    <div>
                        <StatusSummaryBar products={data.products} pollIntervalMs={data.pollIntervalMs} />
                        <div className="flex w-full items-center justify-end gap-3">
                            <span className="text-sm text-neutral-muted">결과는 언제 볼 수 있나요?</span>
                            <HelpTooltip label="결과 확인 방법 안내">
                                먼저 진단이 완료된 상품은 결과 보기 버튼으로 개별로 확인할 수 있어요.{"\n"}
                                전체 상품을 한 번에 보려면 진단이 모드 끝난 후 맨 아래 진단서 보기 버튼을 사용하세요.
                            </HelpTooltip>
                        </div>
                    </div>
                    <ul aria-label="진단 중인 상품" className="flex flex-col gap-4">
                        {data.products.map((product) => (
                            <li key={product.productId}>
                                <ProductProgressCard product={product} />
                            </li>
                        ))}
                    </ul>
                    <div className="flex w-full items-center justify-between">
                        <p id="report-hint" className="text-sm text-neutral-muted">
                            {isDiagnosisDone
                                ? "페이지를 나가도 진단은 계속돼요. 마이페이지에서 다시 볼 수 있어요."
                                : "진행 중인 상품이 끝나면 진단서를 볼 수 있어요."}
                        </p>
                        <Button
                            text="진단서 보기 →"
                            onClick={() => isDiagnosisDone && navigate(`/result/diagnoses/${diagnosesId}`)}
                            fontSize={15}
                            ariaDisabled={!isDiagnosisDone}
                            ariaDescribedBy="report-hint"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}

export default JudgementPage;
