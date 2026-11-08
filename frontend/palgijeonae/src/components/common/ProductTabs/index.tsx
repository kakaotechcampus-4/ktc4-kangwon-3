import { cva } from "class-variance-authority";

import { useIsMobile } from "@/hooks/useIsMobile";
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
    // 모바일은 원본 이름을 넘기고 CSS(truncate)가 자른다. 데스크톱은 글자 수로 줄인다.
    const isMobile = useIsMobile();

    return (
        // 모바일은 한 줄 가로 스크롤. 스크롤 영역에 잘리지 않도록 포커스 링 자리만큼 안쪽 여백을 둔다.
        <div role="tablist" className="no-scrollbar -m-1 flex flex-nowrap items-start gap-2.5 overflow-x-auto p-1 md:flex-wrap md:overflow-visible">
            {productNames.map((name, index) => {
                const displayName = isMobile ? name : truncateWithEllipsis(name, MAX_PRODUCT_NAME_LENGTH);
                return (
                    <button
                        key={index}
                        type="button"
                        role="tab"
                        aria-selected={index === selected}
                        title={isMobile || displayName !== name ? name : undefined}
                        onClick={() => onSelect(index)}
                        className={tabVariants({ selected: index === selected })}
                    >
                        <span className="block max-w-32 truncate md:max-w-none">{displayName}</span>
                    </button>
                );
            })}
        </div>
    );
}

export default ProductTabs;
