import PreviewFrame from "@/components/common/PreviewFrame";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";
import RequiredActionsSection from "@/pages/Result/NextSteps/RequiredActionsSection";
import ResultTabs from "@/pages/Result/ResultTabs";
import { ResultTabKey } from "@/pages/Result/types";

/** 사용 방법 4단계 미리보기: 다음 단계 탭의 해야 할 일 목록. */
function ResultStepPreview() {
    return (
        <PreviewFrame label="진단 결과 화면 미리보기" baseWidth={600}>
            <div className="flex w-full flex-col gap-6">
                <ResultTabs selected={ResultTabKey.NextSteps} onSelect={NOOP} />
                <RequiredActionsSection requiredActions={PREVIEW_PRODUCTS.earphoneResult.requiredActions} />
            </div>
        </PreviewFrame>
    );
}

export default ResultStepPreview;
