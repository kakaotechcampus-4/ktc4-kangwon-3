import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";
import { isMissingRouteParam } from "@/lib/routeParams";

import type { ProductResult } from "./types";
import { useProductResults } from "./useProductResults";

// data가 로딩 중(undefined)일 때 매 렌더 새 배열이 생기지 않도록 고정된 레퍼런스를 재사용한다.
const EMPTY_PRODUCT_RESULTS: ProductResult[] = [];

function ResultPage() {
    const { productId, diagnosesId } = useParams<{ productId?: string; diagnosesId?: string }>();
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);
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

    const { data, isPending, isError, error, refetch } = useProductResults(productId, diagnosesId, isInvalidAccess);
    const products = data ?? EMPTY_PRODUCT_RESULTS;

    const productNames = products.map((product) => product.productName)

    // 존재하지 않는 id로 접근한 경우(404)는 재시도를 띄우지 않고 메인으로 돌려보낸다.
    const isNotFoundError = axios.isAxiosError(error) && error.response?.status === 404;

    useEffect(() => {
        if (isNotFoundError) {
            alert("유효하지 않은 상품/진단서 id 입니다.");
            navigate("/", { replace: true });
        }
    }, [isNotFoundError, navigate]);

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단 결과" description={`${products.length}개 상품에 대한 판정입니다. 상품을 눌러 각각의 근거를 확인하세요.`} />
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
                <div>
                    <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
                </div>
            )}
        </div>
    );
}

export default ResultPage;