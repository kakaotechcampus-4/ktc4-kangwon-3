import type { ProductResult } from "@/api/product";
import SectionIntro from "@/components/common/SectionIntro";

import AttachedImages from "./AttachedImages";
import ProductInfoCard from "./ProductInfoCard";

interface ProductInfoTabProps {
    product: ProductResult
}

function ProductInfoTab({ product }: ProductInfoTabProps) {
    const { productName, sourceType, sourceUrl, sourceText, imageUrls } = product;

    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="진단에 사용한 상품 정보" description="입력하신 상세페이지 정보를 그대로 보여드려요." size="2xl"/>
            <ProductInfoCard productName={productName} sourceType={sourceType} sourceUrl={sourceUrl} sourceText={sourceText} />
            <AttachedImages productName={productName} imageUrls={imageUrls} />
        </div>
    );
}

export default ProductInfoTab;