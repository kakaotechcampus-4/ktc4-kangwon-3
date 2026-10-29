import { useQuery } from "@tanstack/react-query";

import { getProduct } from "@/api/result";

import type { ProductQuestions } from "./types";

async function fetchProductQuestions(productId: string): Promise<ProductQuestions[]> {
    const product = await getProduct(productId);
    return [{
        productId: product.productId,
        productName: product.productName,
        questions: product.questions,
    }];
}

/** 질문 화면에 필요한 상품 하나를 조회한다. */
export function useProductQuestions(productId: string | undefined, enabled: boolean) {
    return useQuery({
        queryKey: ["questions", productId],
        queryFn: () => fetchProductQuestions(productId!),
        enabled,
    });
}
