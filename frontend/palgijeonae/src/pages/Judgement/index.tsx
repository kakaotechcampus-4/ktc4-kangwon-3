import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import SectionIntro from "@/components/common/SectionIntro";
import { isMissingRouteParam } from "@/lib/routeParams";

import { useJudgementProducts } from "./useJudgementProducts";

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

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="상품을 확인하고 있습니다." description="네 명의 전문가가 각자 맡은 법령을 확인합니다." />
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
                // TODO: ProductProgressCard로 교체
                <div className="flex flex-col gap-4">
                    {data.products.map((product) => (
                        <p key={product.productId}>{product.productName} - {product.processingStatus}</p>
                    ))}
                </div>
            )}
        </div>
    );
}

export default JudgementPage;
