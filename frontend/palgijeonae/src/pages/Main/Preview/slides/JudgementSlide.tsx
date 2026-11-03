import PreviewFrame from "@/components/common/PreviewFrame";
import SectionIntro from "@/components/common/SectionIntro";
import ProductProgressCard from "@/pages/Judgement/components/ProductProgressCard";
import StatusSummaryBar from "@/pages/Judgement/components/StatusSummaryBar";
import { PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";

const JUDGEMENT_PRODUCTS = [PREVIEW_PRODUCTS.earphoneInProgress, PREVIEW_PRODUCTS.slipperAwaiting, PREVIEW_PRODUCTS.table];

/** 메인 페이지 미리보기: 진단 진행 화면. */
function JudgementSlide() {
    return (
        <PreviewFrame label="진단 진행 화면 미리보기">
            <div className="flex w-full flex-col gap-8">
                <SectionIntro
                    title="상품을 진단하고 있어요"
                    description="3개 상품을 동시에 확인하고 있어요. 질문이 생긴 상품은 먼저 답해주시면 바로 이어서 진행해요."
                />
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
            </div>
        </PreviewFrame>
    );
}

export default JudgementSlide;
