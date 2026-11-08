import { useState } from "react";

import type { LawAmendment, RecheckProduct } from "@/api/lawAmendments.ts";
import bell from "@/assets/mypage-bell.svg";
import DefaultBox from "@/components/common/DefaultBox";

import AmendmentAccordionItem from "./components/AmendmentAccordionItem.tsx";

interface RevisionNoticeBannerProps {
    lawAmendments: LawAmendment[]
}

function RevisionNoticeBanner({ lawAmendments }: RevisionNoticeBannerProps) {
    // 처음에는 첫 번째 개정만 펼친다.
    const [expandedIds, setExpandedIds] = useState(() => new Set(lawAmendments.slice(0, 1).map((amendment) => amendment.lawAmendmentId)));

    // 같은 상품이 여러 개정에 걸려 있을 수 있어 중복을 뺀다.
    const productCount = new Set(lawAmendments.flatMap((amendment) => amendment.products.map((product) => product.productId))).size;

    const toggle = (lawAmendmentId: string) => {
        setExpandedIds((prev) => {
            const next = new Set(prev);
            if (!next.delete(lawAmendmentId)) {
                next.add(lawAmendmentId);
            }
            return next;
        });
    };

    // 재진단 요청은 다음 커밋에서 연결한다.
    const handleRediagnose = (_product: RecheckProduct) => {};

    return (
        <section aria-label="법령 개정 알림">
            <DefaultBox tone="notice" className="gap-4">
                <div className="flex flex-col gap-2 md:flex-row md:items-center md:gap-3">
                    <div className="flex items-center gap-2 md:gap-3">
                        <img src={bell} alt="" className="size-6 md:size-7" />
                        <span className="rounded-full border border-status-notice bg-white px-3 py-1 text-sm leading-5 font-bold text-status-notice">개정 알림</span>
                    </div>
                    <p className="text-[15px] leading-6 font-bold text-neutral-text md:text-base">
                        법령 개정 <span className="text-status-notice">{lawAmendments.length}건</span> · 다시 진단할 상품 <span className="text-status-notice">{productCount}개</span>
                    </p>
                </div>
                <ul aria-label="법령 개정 목록" className="flex w-full flex-col gap-2">
                    {lawAmendments.map((amendment) => (
                        <AmendmentAccordionItem
                            key={amendment.lawAmendmentId}
                            amendment={amendment}
                            expanded={expandedIds.has(amendment.lawAmendmentId)}
                            onToggle={() => toggle(amendment.lawAmendmentId)}
                            onRediagnose={handleRediagnose}
                        />
                    ))}
                </ul>
                <p className="text-[13px] leading-5 text-neutral-muted">재진단하면 이전 진단 결과는 지워지고, 처음 등록한 내용으로 다시 진단해요.</p>
            </DefaultBox>
        </section>
    );
}

export default RevisionNoticeBanner;
