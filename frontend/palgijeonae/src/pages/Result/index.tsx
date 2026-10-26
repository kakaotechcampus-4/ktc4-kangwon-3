import axios from "axios";
import { type ReactNode, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { ProductResult } from "@/api/product";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import ProductPreview from "@/components/common/ProductPreview";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";
import { isMissingRouteParam } from "@/lib/routeParams";

import DiagnosisResultTab from "./DiagnosisResult";
import NextStepTab from "./NextSteps";
import ProductInfoTab from "./ProductInfo";
import ResultTabs from "./ResultTabs";
import { ResultTabKey } from "./types";
import { useProductResults } from "./useProductResults";


// data가 로딩 중(undefined)일 때 매 렌더 새 배열이 생기지 않도록 고정된 레퍼런스 재사용.
const EMPTY_PRODUCT_RESULTS: ProductResult[] = [];

function ResultPage() {
    const { productId, diagnosesId } = useParams<{ productId?: string; diagnosesId?: string }>();
    const [selectedProductIndex, setSelectedProductIndex] = useState(0);
    const [selectedTab, setSelectedTab] = useState(ResultTabKey.DiagnosisResult);
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
    // product undefined error 방지
    const products = data ?? EMPTY_PRODUCT_RESULTS;

    // 탭에 전달할 productName 배열
    const productNames = products.map((product) => product.productName)

    const currentProduct = products[selectedProductIndex];

    // 존재하지 않는 id로 접근한 경우(404)는 재시도를 띄우지 않고 메인으로 돌려보낸다.
    const isNotFoundError = axios.isAxiosError(error) && error.response?.status === 404;

    useEffect(() => {
        if (isNotFoundError) {
            alert("유효하지 않은 상품/진단서 id 입니다.");
            navigate("/", { replace: true });
        }
    }, [isNotFoundError, navigate]);

    const handleNextStepsClick = () => {
        setSelectedTab(ResultTabKey.NextSteps);
    };

    // TODO: 추후 탭 컴포넌트 props 구현에 따라 수정 필요
    // 선택된 탭에 따라 보여줄 패널
    const tabPanels: Record<ResultTabKey, ReactNode> | null = currentProduct ? {
        [ResultTabKey.DiagnosisResult]: <DiagnosisResultTab
                                            product={currentProduct}
                                            onNextStepsClick={handleNextStepsClick} />,
        [ResultTabKey.NextSteps]: <NextStepTab />,
        [ResultTabKey.ProductInfo]: <ProductInfoTab />,
    } : null;

    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="진단 결과" description={`${products.length}개 상품에 대한 판정입니다. 상품을 눌러 각각의 근거를 확인하세요.`} />
            {isNotFoundError ? null : isPending ? (
                <LoadingSpinner />
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
            ) : !currentProduct || !tabPanels ? (
                <p className="w-full py-12 text-center text-sm font-medium text-neutral-border">
                    표시할 상품이 없어요.
                </p>
            ) : (
                <div className="flex w-full flex-col gap-6">
                    <ProductTabs productNames={productNames} selected={selectedProductIndex} onSelect={setSelectedProductIndex} />
                    <ProductPreview
                        productName={currentProduct.productName}
                        productImageUrl={currentProduct.productImageUrl}
                        resultStatus={currentProduct.resultStatus}
                        processingStatus={currentProduct.processingStatus}
                        sourceType={currentProduct.sourceType}
                    />
                    <ResultTabs selected={selectedTab} onSelect={setSelectedTab} />
                    <div aria-live="polite">
                        {tabPanels[selectedTab]}
                    </div>
                </div>
            )}
        </div>
    );
}

export default ResultPage;