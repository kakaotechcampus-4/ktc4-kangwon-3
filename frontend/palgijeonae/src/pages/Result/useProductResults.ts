import { useQuery } from "@tanstack/react-query";

import type { ProductResult } from "@/api/product";
import { getDiagnosesDetail, getProduct } from "@/api/result";

/** 상품 단건 : productId로 getProduct 호출
 *  진단서 상세 : diagnosesId로 getDiagnosesDetail 호출
 *  productId와 diagnosesId가 모두 없거나, 둘 다 있는 경우는 비정상 접근으로 간주. 쿼리 호출하지 않음
 */
export function useProductResults(
    productId: string | undefined,
    diagnosesId: string | undefined,
    isInvalidAccess: boolean,
) {
    return useQuery({
        queryKey: productId ? ["product", productId] : ["diagnosesDetail", diagnosesId],
        queryFn: async (): Promise<ProductResult[]> => {
            if (productId) {
                // 응답 형태 통일을 위해 배열로 감싸서 반환
                return [await getProduct(productId)];
            }
            return getDiagnosesDetail(diagnosesId!);
        },
        enabled: !isInvalidAccess,
    });
}
