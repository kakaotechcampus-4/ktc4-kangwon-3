import type { SourceType } from "@/api/types/common";
import DefaultBox from "@/components/common/DefaultBox";
import { SOURCE_TYPE_INFO } from "@/constants/statusBadges";
import { cn } from "@/lib/cn";
import { isHttpUrl } from "@/lib/url";

import InfoRow from "./InfoRow";

interface ProductInfoCardProps {
    productName: string
    sourceType: SourceType
    sourceUrl: string | null
    sourceText: string | null
}

const VALUE_CLASS = "text-base text-black md:flex-1";

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
                    {isHttpUrl(sourceUrl) ? (
                        // 값 칸이 flex 항목이라 a를 직접 두면 칸 전체가 클릭돼서, 글자 영역만 클릭되도록 p 안에 둔다.
                        <p className={cn(VALUE_CLASS, "min-w-0 break-all")}>
                            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-primary underline">
                                {sourceUrl}
                            </a>
                        </p>
                    ) : (
                        <p className={cn(VALUE_CLASS, "min-w-0 break-all")}>{sourceUrl}</p>
                    )}
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
