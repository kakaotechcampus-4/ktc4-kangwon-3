import { useId } from "react";

import type { LawAmendment, RecheckProduct } from "@/api/lawAmendments.ts";
import { cn } from "@/lib/cn.ts";

import RecheckProductRow from "./RecheckProductRow.tsx";

interface AmendmentAccordionItemProps {
    amendment: LawAmendment
    expanded: boolean
    onToggle: () => void
    rediagnosingProductId?: string
    onRediagnose: (product: RecheckProduct) => void
}

function AmendmentAccordionItem({ amendment, expanded, onToggle, rediagnosingProductId, onRediagnose }: AmendmentAccordionItemProps) {
    const headerId = useId();
    const panelId = useId();
    const meta = [amendment.revisionType, amendment.enforceDate ? `시행일 ${amendment.enforceDate}` : "시행일 미정"]
        .filter(Boolean)
        .join(" · ");

    return (
        <li className="overflow-hidden rounded-lg border border-neutral-line bg-white">
            <button
                type="button"
                id={headerId}
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={onToggle}
                className="flex min-h-14 w-full cursor-pointer items-center gap-3 p-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-inset focus-visible:ring-status-notice/30 md:min-h-13 md:py-3.5"
            >
                <span className="min-w-0 flex-1 text-[15px] leading-5.5 font-bold wrap-break-word text-neutral-text md:text-base md:leading-6">
                    {amendment.lawName}
                </span>
                <span className="shrink-0 rounded-full bg-status-notice-bg px-2.5 py-0.75 text-[13px] leading-4.5 font-bold text-status-notice">
                    상품 {amendment.products.length}개
                </span>
                <svg
                    aria-hidden
                    viewBox="0 0 20 20"
                    className={cn("size-5 shrink-0 text-neutral-dark transition-transform motion-reduce:transition-none", expanded && "rotate-180")}
                >
                    <path d="M5 7.5 10 12.5l5-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </button>
            <div
                id={panelId}
                role="region"
                aria-labelledby={headerId}
                hidden={!expanded}
                className="border-t border-neutral-line px-4 pt-1 pb-2"
            >
                <p className="pt-2 pb-1 text-sm font-medium text-status-notice">{meta}</p>
                <ul aria-label={`${amendment.lawName} 재진단 대상 상품`} className="divide-y divide-neutral-line">
                    {amendment.products.map((product) => (
                        <RecheckProductRow
                            key={product.productId}
                            product={product}
                            isPending={rediagnosingProductId === product.productId}
                            onRediagnose={() => onRediagnose(product)}
                        />
                    ))}
                </ul>
            </div>
        </li>
    );
}

export default AmendmentAccordionItem;
