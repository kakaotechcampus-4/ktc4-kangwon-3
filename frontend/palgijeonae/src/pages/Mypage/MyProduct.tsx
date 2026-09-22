import { cva } from "class-variance-authority";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import DefaultBox from "@/components/common/DefaultBox";

import type { ProductInputType, ResultStatus } from "./types.ts";

interface MyProductProps {
    title: string
    thumbnail?: string
    inputType: ProductInputType
    resultStatus: ResultStatus
    link?: string
    content?: string
    images?: string[]
}

const RESULT_STATUS_LABELS: Record<ResultStatus, string> = {
    PURCHASING_AGENT_ALLOWED: "구매 대행 가능",
    DIRECT_IMPORT_CERTIFICATION_REQUIRED: "사입 인증 필요",
    RECHECK_REQUIRED: "재확인 필요",
};

// 첫 번째 인자(base)는 상태와 무관하게 항상 붙는 공통 스타일(모양/크기 등), variants.resultStatus 안은 상태별로 달라지는 색만.
const resultStatusBadgeVariants = cva("px-2.5 py-1 border rounded-full text-sm font-semibold", {
    variants: {
        resultStatus: {
            PURCHASING_AGENT_ALLOWED: "text-status-success bg-status-success-bg",
            DIRECT_IMPORT_CERTIFICATION_REQUIRED: "text-status-danger bg-status-danger-bg",
            RECHECK_REQUIRED: "text-status-warning bg-status-warning-bg",
        },
    },
});

function MyProduct({ title, resultStatus, thumbnail }: MyProductProps) {
    return (
        <DefaultBox>
            <div className="flex flex-row w-full gap-4 cursor-pointer">
                <img src={thumbnail ?? defaultThumbnail}
                    alt="상품 썸네일"
                    className="w-20 h-20 object-cover rounded-lg border border-neutral-border" />
                <div className="flex flex-col items-start gap-2">
                    <div className={resultStatusBadgeVariants({ resultStatus })}>
                        {RESULT_STATUS_LABELS[resultStatus]}
                    </div>
                    <h3 className="text-lg font-semibold pl-1">{title}</h3>
                </div>
            </div>
        </DefaultBox>
    );
}

export default MyProduct;
