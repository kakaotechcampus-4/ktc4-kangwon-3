import axios from "axios";
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { isMissingRouteParam } from "@/lib/routeParams";

import { useProductResults } from "./useProductResults";

function ResultPage() {
    const { productId, diagnosesId } = useParams<{ productId?: string; diagnosesId?: string }>();
    const navigate = useNavigate();

    const isMissingProductId = isMissingRouteParam(productId);
    const isMissingDiagnosesId = isMissingRouteParam(diagnosesId);
    // 파라미터 값이 둘 다 있거나, 둘 다 없는 경우 비정상 접근
    const isInvalidAccess = isMissingProductId === isMissingDiagnosesId;

    useEffect(() => {
        if (isInvalidAccess) {
            alert("잘못된 접근입니다.");
            navigate("/", { replace: true });
        }
    }, [isInvalidAccess, navigate]);

    const { data: products, isPending, isError, error, refetch } = useProductResults(productId, diagnosesId, isInvalidAccess);
    
    // 존재하지 않는 id로 접근한 경우(404)는 재시도를 띄우지 않고 메인으로 돌려보낸다.
    const isNotFoundError = axios.isAxiosError(error) && error.response?.status === 404;

    useEffect(() => {
        if (isNotFoundError) {
            alert("유효하지 않은 상품/진단서 id 입니다.");
            navigate("/", { replace: true });
        }
    }, [isNotFoundError, navigate]);

    return (
        <div>
            <h1>결과 페이지 입니다.</h1>
            {isNotFoundError ? null : isPending ? (
                <div className="flex w-full justify-center py-12">
                    <div className="h-10 w-10 animate-spin rounded-full border-4 border-neutral-border border-t-white" />
                </div>
            ) : isError ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-status-danger">결과를 불러오지 못했어요.</p>
                    <button
                        type="button"
                        onClick={() => refetch()}
                        className="text-sm font-medium cursor-pointer text-neutral-border underline underline-offset-2"
                    >
                        다시 시도
                    </button>
                </div>
            ) : (
                <div>{/*TODO: 결과 표시 로직 구현. unused error을 피하기 위한 product.length 사용*/}{products.length}</div>
            )}
        </div>
     );
}

export default ResultPage;