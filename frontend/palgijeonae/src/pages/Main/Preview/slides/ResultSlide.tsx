import PreviewFrame from "@/components/common/PreviewFrame";
import ProductTabs from "@/components/common/ProductTabs";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";
import DiagnosisResultTab from "@/pages/Result/DiagnosisResult";
import ResultTabs from "@/pages/Result/ResultTabs";
import { ResultTabKey } from "@/pages/Result/types";

const PRODUCT_NAMES = [
    PREVIEW_PRODUCTS.earphoneResult.productName,
    PREVIEW_PRODUCTS.table.productName,
    PREVIEW_PRODUCTS.slipperResult.productName,
];

// 미리보기는 길어지지 않도록 분야별 검토 카드를 1개만 보여준다(요약 배너의 "해야 할 일" 건수는 그대로 유지).
const RESULT_PREVIEW_PRODUCT = {
    ...PREVIEW_PRODUCTS.earphoneResult,
    toolReviews: PREVIEW_PRODUCTS.earphoneResult.toolReviews.slice(0, 1),
};

/** 메인 페이지 미리보기: 진단 결과 화면. */
function ResultSlide() {
    return (
        <PreviewFrame label="진단 결과 화면 미리보기" baseWidth={600} maxHeight={520}>
            <div className="flex w-full flex-col gap-6">
                <ProductTabs productNames={PRODUCT_NAMES} selected={0} onSelect={NOOP} />
                <ResultTabs selected={ResultTabKey.DiagnosisResult} onSelect={NOOP} />
                <DiagnosisResultTab product={RESULT_PREVIEW_PRODUCT} onNextStepsClick={NOOP} />
            </div>
        </PreviewFrame>
    );
}

export default ResultSlide;
