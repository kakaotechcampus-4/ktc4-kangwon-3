import { useState } from "react";

import type { ProductResult } from "@/api/product";
import { ProcessingStatusType } from "@/api/types";
import { truncateWithEllipsis } from "@/lib/text";

// 스크린리더로 알릴 상태만. 진행 중으로 바뀌는 건(PENDING → IN_PROGRESS, 답변 후 재진행) 알리지 않는다.
const ANNOUNCE_TEXT: Partial<Record<ProcessingStatusType, string>> = {
    [ProcessingStatusType.AwaitingInput]: "답변이 필요해요",
    [ProcessingStatusType.Completed]: "진단이 끝났어요",
    [ProcessingStatusType.Failed]: "진단에 실패했어요",
};

// 카드에 보이는 상품명 길이와 맞춘다.
const MAX_PRODUCT_NAME_LENGTH = 30;

/**
 * 폴링 응답 사이에 상태가 바뀐 상품을 한 문장으로 모아 돌려준다.
 * - 첫 응답(페이지 진입)은 알리지 않는다.
 * - react-query는 데이터가 같으면 같은 참조를 돌려주므로, 참조가 바뀐 응답만 비교한다.
 */
export function useStatusAnnouncement(products: ProductResult[] | undefined, isDone: boolean) {
    const [prevProducts, setPrevProducts] = useState(products);
    const [message, setMessage] = useState("");

    // 렌더 중 상태 조정 패턴
    if (products !== prevProducts) {
        setPrevProducts(products);
        if (prevProducts && products) {
            const prevStatus = new Map(prevProducts.map((p) => [p.productId, p.processingStatus]));
            const changes = products
                .filter((p) => prevStatus.get(p.productId) !== p.processingStatus && ANNOUNCE_TEXT[p.processingStatus])
                .map((p) => `${truncateWithEllipsis(p.productName, MAX_PRODUCT_NAME_LENGTH)} ${ANNOUNCE_TEXT[p.processingStatus]}`);
            if (isDone) changes.push("모든 진단이 끝났어요. 진단서를 볼 수 있어요");
            if (changes.length > 0) setMessage(changes.join(". "));
        }
    }

    return message;
}
