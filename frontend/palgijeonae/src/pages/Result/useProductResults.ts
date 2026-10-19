import { useQuery } from "@tanstack/react-query";

import type { ProductResult } from "@/api/product";
import { getDiagnosesDetail, getProduct } from "@/api/result";

// 상품 단건(마이페이지)과 진단서 단위(질문 페이지) 두 조회를 같은 형태(ProductResult[])로 합쳐서 반환한다.
// 라우트 구조상 productId/diagnosesId는 동시에 채워질 수 없고, isInvalidAccess(ResultPage에서 계산)가
// false인 시점엔 둘 중 하나만 유효하다는 게 보장되므로 productId 자체로 분기한다.
export function useProductResults(
    productId: string | undefined,
    diagnosesId: string | undefined,
    isInvalidAccess: boolean,
) {
    return useQuery({
        queryKey: productId ? ["product", productId] : ["diagnosesDetail", diagnosesId],
        queryFn: async (): Promise<ProductResult[]> => {
            if (productId) {
                return [await getProduct(productId)];
            }
            return getDiagnosesDetail(diagnosesId!);
        },
        enabled: !isInvalidAccess,
    });
}
