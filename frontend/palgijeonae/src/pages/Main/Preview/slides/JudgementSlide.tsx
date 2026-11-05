import PreviewFrame from "@/components/common/PreviewFrame";
import ProductProgressCard from "@/pages/Judgement/components/ProductProgressCard";
import StatusSummaryBar from "@/pages/Judgement/components/StatusSummaryBar";
import { PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";

const JUDGEMENT_PRODUCTS = [PREVIEW_PRODUCTS.earphoneInProgress, PREVIEW_PRODUCTS.slipperAwaiting, PREVIEW_PRODUCTS.table];

/** 메인 페이지 미리보기: 진단 진행 화면. */
function JudgementSlide() {
    return (
        <PreviewFrame label="진단 진행 화면 미리보기" baseWidth={1000} maxHeight={520}>
            <div className="flex w-full flex-col gap-6">
                <StatusSummaryBar products={JUDGEMENT_PRODUCTS} pollIntervalMs={3000} />
                <ul className="flex flex-col gap-4">
                    {JUDGEMENT_PRODUCTS.map((product) => (
                        <li key={product.productId}>
                            <ProductProgressCard product={product} />
                        </li>
                    ))}
                </ul>
            </div>
        </PreviewFrame>
    );
}

export default JudgementSlide;
