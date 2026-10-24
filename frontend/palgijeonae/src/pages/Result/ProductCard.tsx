import type { ProcessingStatusType, ResultStatus, SourceType } from "@/api/types";
import DefaultBox from "@/components/common/DefaultBox";
import ProductSummary from "@/components/common/ProductSummary";

interface ProductCardProps {
    productName: string
    productImageUrl?: string | null
    resultStatus: ResultStatus | null
    processingStatus: ProcessingStatusType
    sourceType: SourceType
}

function ProductCard({ productName, productImageUrl, resultStatus, processingStatus, sourceType }: ProductCardProps) {
    return (
        <DefaultBox>
            <ProductSummary
                productName={productName}
                productImageUrl={productImageUrl}
                resultStatus={resultStatus}
                processingStatus={processingStatus}
                sourceType={sourceType}
            />
        </DefaultBox>
    );
}

export default ProductCard;
