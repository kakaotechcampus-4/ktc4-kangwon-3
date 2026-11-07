import { ProcessingStatusType } from "@/api/types/common";
import type { ProductResult } from "@/api/types/product";

export interface StatusNotice {
    text: string
    className: string
}

const AWAITING_INPUT_NOTICE_TEXT = "답변하면 처음부터 다시 진단해요. 다른 상품은 기다리지 않고 계속 진행돼요.";

/** 카드 하단 안내 박스. 답변 대기는 고정 문구, 실패는 에러 메시지를 보여준다. 그 외엔 안내가 없다. */
export function getStatusNotice(product: ProductResult): StatusNotice | null {
    switch (product.processingStatus) {
        case ProcessingStatusType.AwaitingInput:
            return { text: AWAITING_INPUT_NOTICE_TEXT, className: "bg-status-warning-bg text-status-warning" };
        case ProcessingStatusType.Failed:
            return product.failure
                ? { text: product.failure.errorMessage, className: "bg-status-danger-bg text-status-danger" }
                : null;
        default:
            return null;
    }
}
