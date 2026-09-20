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
    count: number
    selected: number
    onSelect: (index: number) => void
}

function ProductTabs({ count, selected, onSelect }: ProductTabsProps) {
    return (
        <div className="flex flex-wrap items-start gap-2.5">
            {Array.from({ length: count }, (_, index) => (
                <button
                    key={index}
                    type="button"
                    onClick={() => onSelect(index)}
                    className={tabVariants({ selected: index === selected })}
                >
                    제품 {index + 1}
                </button>
            ))}
        </div>
    );
}

export default ProductTabs;
