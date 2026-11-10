import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteProduct } from "@/api/products.ts";
import { LAW_AMENDMENTS_QUERY_KEY } from "@/pages/Products/constants.ts";

// 상품 단건 삭제. 성공하면 목록을 다시 불러온다. 삭제한 상품은 개정 알림 대상에서도 빠진다.
export function useDeleteProduct() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: deleteProduct,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["myProducts"] });
            queryClient.invalidateQueries({ queryKey: LAW_AMENDMENTS_QUERY_KEY });
        },
    });
}
