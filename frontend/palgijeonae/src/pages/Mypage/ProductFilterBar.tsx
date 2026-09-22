import type { ProductFilter } from "./types.ts";

interface ProductFilterBarProps {
    searchTerm: string
    onSearchTermChange: (value: string) => void
    filter: ProductFilter
    onFilterChange: (filter: ProductFilter) => void
}

function ProductFilterBar(_props: ProductFilterBarProps) {
    return (
        <div>
            검색 / 필터
        </div>
    );
}

export default ProductFilterBar;
