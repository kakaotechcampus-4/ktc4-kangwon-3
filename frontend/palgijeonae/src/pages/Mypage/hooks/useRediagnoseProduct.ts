import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/core/client.ts";
import type { RecheckProduct } from "@/api/lawAmendments.ts";
import { rediagnoseProduct } from "@/api/products.ts";
import { LAW_AMENDMENTS_QUERY_KEY } from "@/pages/Mypage/constants.ts";

// 진단을 마친 상품 재진단. 성공하면 관련 목록을 다시 불러오고 진행 화면으로 이동한다.
export function useRediagnoseProduct() {
    const queryClient = useQueryClient();
    const navigate = useNavigate();

    return useMutation({
        mutationFn: (product: RecheckProduct) => rediagnoseProduct(product.productId),
        onSuccess: (_data, product) => {
            queryClient.invalidateQueries({ queryKey: LAW_AMENDMENTS_QUERY_KEY });
            queryClient.invalidateQueries({ queryKey: ["myProducts"] });
            queryClient.invalidateQueries({ queryKey: ["product", product.productId] });
            navigate(`/judgement/${product.diagnosesId}`);
        },
        onError: (error) => {
            alert(getErrorMessage(error, "재진단 요청에 실패했어요. 다시 시도해주세요."));
        },
    });
}
