import type { SourceType } from "@/api/types";
import DefaultBox from "@/components/common/DefaultBox";
import { SOURCE_TYPE_INFO } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";

import InfoRow from "./InfoRow";

interface ProductInfoCardProps {
    productName: string
    sourceType: SourceType
    sourceUrl: string | null
    sourceText: string | null
}

const VALUE_CLASS = "flex-1 text-base text-black";

function ProductInfoCard({ productName, sourceType, sourceUrl, sourceText }: ProductInfoCardProps) {
    return (
        <DefaultBox>
            <InfoRow label="상품명">
                <p className={VALUE_CLASS}>{productName}</p>
            </InfoRow>
            <InfoRow label="입력 방식">
                <p className={VALUE_CLASS}>{SOURCE_TYPE_INFO[sourceType].label}</p>
            </InfoRow>
            {sourceUrl && (
                <InfoRow label="상세페이지">
                    <a
                        href={sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={cn(VALUE_CLASS, "text-primary underline")}
                    >
                        {sourceUrl}
                    </a>
                </InfoRow>
            )}
            {sourceText && (
                <InfoRow label="입력 내용">
                    <p className={cn(VALUE_CLASS, "rounded-xl bg-gray-100 px-4 py-3 whitespace-pre-line")}>
                        {sourceText}
                    </p>
                </InfoRow>
            )}
        </DefaultBox>
    );
}

export default ProductInfoCard;
