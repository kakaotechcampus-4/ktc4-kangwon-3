import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";

import { getProgressDescription } from "./progressDescription";

interface ProductProgressCardProps {
    product: ProductResult
}

function ProductProgressCard({ product }: ProductProgressCardProps) {
    const { processingStatus, progresses, summary, failure } = product;

    // 진행 중일 때의 설명
    const progressDescription = processingStatus === ProcessingStatusType.InProgress
        ? getProgressDescription(progresses)
        : null;

    // 완료/실패일 때의 설명
    const completedSummary = processingStatus === ProcessingStatusType.Completed ? summary : null;
    const failureMessage = processingStatus === ProcessingStatusType.Failed ? failure?.errorMessage ?? null : null;

    // TODO: 컴포넌트 구성(레이아웃/스타일)은 다음 단계에서 진행. 지금은 파싱한 값만 확인.
    // TODO: 답변 대기 중 질문 개수는 회차(questionRound)를 고려해서 세야 함 - questions.length는 과거 회차까지 포함해 부정확함
    return (
        <div>
            상품 진행 카드: {progressDescription ?? completedSummary ?? failureMessage ?? "답변 대기 중"}
        </div>
    );
}

export default ProductProgressCard;
