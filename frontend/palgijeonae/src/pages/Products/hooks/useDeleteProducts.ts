import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteProduct } from "@/api/products.ts";
import { LAW_AMENDMENTS_QUERY_KEY } from "@/pages/Products/constants.ts";

interface DeleteProductsResult {
    deletedIds: string[]
    failedIds: string[]
    // 실패한 요청 중 첫 번째 오류. 실패가 없으면 undefined
    firstError: unknown
}

// 여러 상품 삭제. 백엔드에 다건 삭제 API가 없어 단건 삭제를 동시에 여러 번 부른다.
// 일부가 실패해도 throw하지 않고 성공·실패 id를 나눠 돌려준다. 끝나면 목록과 개정 알림을 한 번씩만 다시 불러온다.
export function useDeleteProducts() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (productIds: string[]): Promise<DeleteProductsResult> => {
            const results = await Promise.allSettled(productIds.map(deleteProduct));
            const deletedIds: string[] = [];
            const failedIds: string[] = [];
            let firstError: unknown;

            results.forEach((result, index) => {
                if (result.status === "fulfilled") {
                    deletedIds.push(productIds[index]);
                } else {
                    failedIds.push(productIds[index]);
                    firstError ??= result.reason;
                }
            });

            return { deletedIds, failedIds, firstError };
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey: ["myProducts"] });
            queryClient.invalidateQueries({ queryKey: LAW_AMENDMENTS_QUERY_KEY });
        },
    });
}
