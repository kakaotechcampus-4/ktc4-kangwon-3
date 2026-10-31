import type { ProductResult } from "@/api/product";

import { getStatusDescription } from "./statusDescription";

interface ProductProgressCardProps {
    product: ProductResult
}

function ProductProgressCard({ product }: ProductProgressCardProps) {
    const description = getStatusDescription(product);

    // TODO: 컴포넌트 구성(레이아웃/스타일)은 다음 단계에서 진행. 지금은 파싱한 값만 확인.
    return (
        <div>
            상품 진행 카드: {description}
        </div>
    );
}

export default ProductProgressCard;
