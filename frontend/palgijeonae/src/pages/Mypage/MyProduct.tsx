import { Link } from "react-router-dom";

import DefaultBox from "@/components/common/DefaultBox";
import ProductSummary from "@/components/common/ProductSummary";

import type { MyProductItem } from "./types.ts";

type MyProductProps = MyProductItem;

function MyProduct({ productId, productName, productImageUrl, sourceType, processingStatus, resultStatus }: MyProductProps) {
    // 진단 결과가 없을 시 진단서 이동을 막기 위한 boolean 변수.
    const isDiagnosisComplete = resultStatus != null;

    const summary = (
        <ProductSummary
            productName={productName}
            productImageUrl={productImageUrl}
            resultStatus={resultStatus}
            processingStatus={processingStatus}
            sourceType={sourceType}
        />
    );

    return (
        <DefaultBox>
            {isDiagnosisComplete ? (
                <Link to={`/result/product/${productId}`} className="w-full cursor-pointer">
                    {summary}
                </Link>
            ) : (
                <div className="w-full">
                    {summary}
                </div>
            )}
        </DefaultBox>
    );
}

export default MyProduct;
