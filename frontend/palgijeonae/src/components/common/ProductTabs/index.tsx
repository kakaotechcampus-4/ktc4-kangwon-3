interface ProductTabsProps {
    count: number
    selected: number
    onSelect: (index: number) => void
}

function ProductTabs({ count, selected, onSelect }: ProductTabsProps) {
    return (
        <div className="flex flex-wrap items-start gap-2.5">
            {Array.from({ length: count }, (_, index) => {
                const isSelected = index === selected;
                return (
                    <button
                        key={index}
                        type="button"
                        onClick={() => onSelect(index)}
                        className={`shrink-0 rounded-[20px] border px-[15px] py-[7px] text-base font-medium ${
                            isSelected
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-neutral-border bg-white text-neutral-border"
                        }`}
                    >
                        제품 {index + 1}
                    </button>
                );
            })}
        </div>
    );
}

export default ProductTabs;
