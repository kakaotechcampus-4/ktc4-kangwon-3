import PreviewFrame from "@/components/common/PreviewFrame";
import ProductProgressCard from "@/pages/Judgement/components/ProductProgressCard";
import StatusSummaryBar from "@/pages/Judgement/components/StatusSummaryBar";
import { PREVIEW_PRODUCTS } from "@/pages/Main/constants";

import ReturnPathGuide from "./ReturnPathGuide";

const JUDGEMENT_STEP_PRODUCTS = [PREVIEW_PRODUCTS.earphoneInProgress, PREVIEW_PRODUCTS.slipperAwaiting, PREVIEW_PRODUCTS.table];

/** 사용 방법 2단계 미리보기: 진단 진행 중 화면과, 화면을 떠났다 돌아오는 방법. */
function JudgementStepPreview() {
    return (
        <PreviewFrame label="진단 진행 화면 미리보기" baseWidth={600}>
            <div className="flex w-full flex-col gap-6">
                <StatusSummaryBar products={JUDGEMENT_STEP_PRODUCTS} />
                <ProductProgressCard product={PREVIEW_PRODUCTS.earphoneInProgress} />
                <ReturnPathGuide />
            </div>
        </PreviewFrame>
    );
}

export default JudgementStepPreview;
