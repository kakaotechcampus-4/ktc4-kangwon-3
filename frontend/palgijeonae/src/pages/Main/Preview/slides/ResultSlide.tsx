import PreviewFrame from "@/components/common/PreviewFrame";
import ProductTabs from "@/components/common/ProductTabs";
import SectionIntro from "@/components/common/SectionIntro";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";
import DiagnosisResultTab from "@/pages/Result/DiagnosisResult";
import ResultTabs from "@/pages/Result/ResultTabs";
import { ResultTabKey } from "@/pages/Result/types";

const PRODUCT_NAMES = [
    PREVIEW_PRODUCTS.earphoneResult.productName,
    PREVIEW_PRODUCTS.table.productName,
    PREVIEW_PRODUCTS.slipperResult.productName,
];

/** 메인 페이지 미리보기: 진단 결과 화면. */
function ResultSlide() {
    return (
        <PreviewFrame label="진단 결과 화면 미리보기">
            <div className="flex w-full flex-col gap-8">
                <SectionIntro
                    title="진단 결과"
                    description="3개 상품에 대한 판정입니다. 상품을 눌러 각각의 근거를 확인하세요."
                />
                <div className="flex w-full flex-col gap-6">
                    <ProductTabs productNames={PRODUCT_NAMES} selected={0} onSelect={NOOP} />
                    <ResultTabs selected={ResultTabKey.DiagnosisResult} onSelect={NOOP} />
                    <DiagnosisResultTab product={PREVIEW_PRODUCTS.earphoneResult} onNextStepsClick={NOOP} />
                </div>
            </div>
        </PreviewFrame>
    );
}

export default ResultSlide;
