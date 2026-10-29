import { useQuery } from "@tanstack/react-query";

import { getProduct } from "@/api/result";

import type { QuestionProduct } from "./types";

async function fetchQuestionProduct(productId: string): Promise<QuestionProduct> {
    const product = await getProduct(productId);
    return {
        productId: product.productId,
        productName: product.productName,
        productImageUrl: product.productImageUrl,
        resultStatus: product.resultStatus,
        processingStatus: product.processingStatus,
        sourceType: product.sourceType,
        questions: product.questions,
    };
}

/** 질문 화면에 필요한 상품 하나를 조회한다. */
export function useQuestionProduct(productId: string | undefined, enabled: boolean) {
    return useQuery({
        queryKey: ["questions", productId],
        queryFn: () => fetchQuestionProduct(productId!),
        enabled,
    });
}
