import { cva } from "class-variance-authority";

import { truncateWithEllipsis } from "@/lib/text";

const tabVariants = cva("shrink-0 cursor-pointer rounded-full border px-3.75 py-1.75 text-base font-medium transition-colors duration-150 outline-none focus-visible:ring-3 focus-visible:ring-primary/25", {
    variants: {
        selected: {
            true: "border-primary/40 bg-primary-soft text-primary",
            false: "border-box-line bg-white text-neutral-muted hover:bg-button-hover-bg",
        },
    },
});

interface ProductTabsProps {
    productNames: string[]
    selected: number
    onSelect: (index: number) => void
}

// 상품명을 몇 글자까지 보여줄 지 결정
const MAX_PRODUCT_NAME_LENGTH = 10;

function ProductTabs({ productNames, selected, onSelect }: ProductTabsProps) {
    return (
        <div role="tablist" className="flex flex-wrap items-start gap-2.5">
            {productNames.map((name, index) => (
                <button
                    key={index}
                    type="button"
                    role="tab"
                    aria-selected={index === selected}
                    onClick={() => onSelect(index)}
                    className={tabVariants({ selected: index === selected })}
                >
                    {truncateWithEllipsis(name, MAX_PRODUCT_NAME_LENGTH)}
                </button>
            ))}
        </div>
    );
}

export default ProductTabs;
