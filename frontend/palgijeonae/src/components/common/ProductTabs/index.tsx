import { cva } from "class-variance-authority";

const tabVariants = cva("shrink-0 rounded-[20px] border px-[15px] py-[7px] text-base font-medium", {
    variants: {
        selected: {
            true: "border-primary bg-primary/10 text-primary",
            false: "border-neutral-border bg-white text-neutral-border",
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

const truncateProductName = (name: string) =>
    name.length > MAX_PRODUCT_NAME_LENGTH ? `${name.slice(0, MAX_PRODUCT_NAME_LENGTH)}...` : name;

function ProductTabs({ productNames, selected, onSelect }: ProductTabsProps) {
    return (
        <div className="flex flex-wrap items-start gap-2.5">
            {productNames.map((name, index) => (
                <button
                    key={index}
                    type="button"
                    onClick={() => onSelect(index)}
                    className={tabVariants({ selected: index === selected })}
                >
                    {truncateProductName(name)}
                </button>
            ))}
        </div>
    );
}

export default ProductTabs;
