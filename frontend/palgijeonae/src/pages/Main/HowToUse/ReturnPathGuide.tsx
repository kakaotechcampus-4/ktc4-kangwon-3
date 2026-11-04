import type { ReactNode } from "react";

import DefaultBox from "@/components/common/DefaultBox";
import ProductPreview from "@/components/common/ProductPreview";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";
import ResultBanner from "@/pages/Result/DiagnosisResult/ResultBanner";

import MiniHeaderPreview from "./MiniHeaderPreview";

interface ReturnPathRowProps {
    number: number
    children: ReactNode
    preview: ReactNode
}

function ReturnPathRow({ number, children, preview }: ReturnPathRowProps) {
    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-start gap-2 text-xs text-neutral-text">
                <span className="flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-full bg-[#E7EEFB] text-xs font-bold text-primary">
                    {number}
                </span>
                {children}
            </div>
            <div className="ml-6.5">{preview}</div>
        </div>
    );
}

const JUDGEMENT_PREVIEW_PATH = "/judgement/preview-diagnoses";

/** 진단 진행 화면에서 벗어났다가 다시 돌아오는 3가지 경로 안내. */
function ReturnPathGuide() {
    return (
        <DefaultBox variant="dashed" align="left" className="gap-2">
            <p className="text-sm font-bold text-black">화면을 떠났다면 이렇게 돌아와요</p>
            <ReturnPathRow number={1} preview={<MiniHeaderPreview />}>
                오른쪽 위 <b className="font-semibold text-black">마이페이지</b> 클릭
            </ReturnPathRow>
            <ReturnPathRow
                number={2}
                preview={
                    <ProductPreview
                        productName={PREVIEW_PRODUCTS.earphoneInProgress.productName}
                        productImageUrl={PREVIEW_PRODUCTS.earphoneInProgress.productImageUrl}
                        resultStatus={PREVIEW_PRODUCTS.earphoneInProgress.resultStatus}
                        processingStatus={PREVIEW_PRODUCTS.earphoneInProgress.processingStatus}
                        sourceType={PREVIEW_PRODUCTS.earphoneInProgress.sourceType}
                    />
                }
            >
                진행 중인 <b className="font-semibold text-black">상품</b> 클릭
            </ReturnPathRow>
            <ReturnPathRow
                number={3}
                preview={
                    <ResultBanner
                        product={PREVIEW_PRODUCTS.earphoneInProgress}
                        judgementPath={JUDGEMENT_PREVIEW_PATH}
                        onNextStepsClick={NOOP}
                    />
                }
            >
                배너의 <b className="font-semibold text-black">진행 상황 확인</b> 버튼 클릭
            </ReturnPathRow>
        </DefaultBox>
    );
}

export default ReturnPathGuide;
