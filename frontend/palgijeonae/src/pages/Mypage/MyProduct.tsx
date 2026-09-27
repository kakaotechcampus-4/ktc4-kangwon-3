import { cva } from "class-variance-authority";
import { useNavigate } from "react-router-dom";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import DefaultBox from "@/components/common/DefaultBox";

import type { MyProductItem, ResultStatus } from "./types.ts";

type MyProductProps = MyProductItem;

// 상품 결과(ResultStatus) 텍스트 매핑
const RESULT_STATUS_LABELS: Record<ResultStatus, string> = {
    PURCHASING_AGENT_ALLOWED: "구매 대행 가능",
    DIRECT_IMPORT_CERTIFICATION_REQUIRED: "사입 인증 필요",
    RECHECK_REQUIRED: "재확인 필요",
};

// 상품 결과(ResultStatus) 태그 스타일링
const resultStatusBadgeVariants = cva("px-2.5 py-1 border rounded-full text-sm font-semibold", {
    variants: {
        resultStatus: {
            PURCHASING_AGENT_ALLOWED: "text-status-success bg-status-success-bg",
            DIRECT_IMPORT_CERTIFICATION_REQUIRED: "text-status-danger bg-status-danger-bg",
            RECHECK_REQUIRED: "text-status-warning bg-status-warning-bg",
        },
    },
});

function MyProduct({ productName, resultStatus, productImageUrl }: MyProductProps) {
    const navigate = useNavigate();

    return (
        <DefaultBox>
            {/* TODO: Result 페이지 구현 시 /result/product?productId=로 변경. */}
            <div
                className="flex flex-row w-full gap-4 cursor-pointer"
                onClick={() => navigate("/result")}
            >
                <img src={productImageUrl ?? defaultThumbnail}
                    alt="상품 썸네일"
                    className="w-20 h-20 object-cover rounded-lg border border-neutral-border" />
                <div className="flex flex-col items-start gap-2">
                    <div className={resultStatusBadgeVariants({ resultStatus })}>
                        {RESULT_STATUS_LABELS[resultStatus]}
                    </div>
                    <h3 className="text-lg font-semibold pl-1">{productName}</h3>
                </div>
            </div>
        </DefaultBox>
    );
}

export default MyProduct;
