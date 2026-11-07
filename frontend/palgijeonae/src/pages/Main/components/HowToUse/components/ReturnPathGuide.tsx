import type { ReactNode } from "react";

import DefaultBox from "@/components/common/DefaultBox";
import ProductPreview from "@/components/common/ProductPreview";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/constants";
import ResultBanner from "@/pages/Result/components/DiagnosisResult/components/ResultBanner";

import MiniHeaderPreview from "./MiniHeaderPreview";

// 설명 글에 비해 미리보기 요소가 커 보이지 않도록 줄이는 배율.
const PREVIEW_ZOOM = 0.6;

interface ReturnPathRowProps {
    number: number
    children: ReactNode
    preview: ReactNode
}

/** 복귀 경로 안내의 한 행. 번호와 설명 문구 아래에 해당 경로의 미리보기를 줄여서 보여준다. */
function ReturnPathRow({ number, children, preview }: ReturnPathRowProps) {
    return (
        <div className="flex w-full flex-col gap-2">
            <div className="flex items-center gap-2 text-base text-neutral-text">
                <span className="flex h-4.5 w-4.5 shrink-0 items-center justify-center rounded-ful text-base font-bold text-primary">
                    {number}
                </span>
                {children}
            </div>
            <div className="ml-6.5 min-w-0">
                <div inert className="select-none" style={{ zoom: PREVIEW_ZOOM }}>
                    {preview}
                </div>
            </div>
        </div>
    );
}

const JUDGEMENT_PREVIEW_PATH = "/judgement/preview-diagnoses";

/** 진단 진행 화면에서 벗어났다가 다시 돌아오는 3가지 경로 안내. */
function ReturnPathGuide() {
    return (
        <DefaultBox variant="dashed" align="left" className="gap-2">
            <p className="text-lg font-bold text-black">화면을 떠났다면 이렇게 돌아와요</p>
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
