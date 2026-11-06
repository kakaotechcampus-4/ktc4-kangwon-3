import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteProduct } from "@/api/myProducts.ts";

// 상품 단건 삭제. 성공하면 목록을 다시 불러온다.
export function useDeleteProduct() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: deleteProduct,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["myProducts"] });
        },
    });
}
