import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import type { Product } from "@/pages/Upload/types.ts";

import AddedProduct from "./AddedProduct.tsx";

// 자세히 보기 모달을 연결하기 전까지는 항목을 눌러도 아무 일도 하지 않는다.
const NOOP = () => {};

interface AddedProductListProps {
    products: Product[]
    onRemove: (id: string) => void
}

function AddedProductList({ products, onRemove }: AddedProductListProps) {
    if (products.length === 0) {
        return null;
    }

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <SectionIntro title="확인할 제품" size="2xl" />
            <div className="flex w-full flex-col gap-3">
                {products.map((product) => (
                    <AddedProduct
                        key={product.id}
                        type={product.type}
                        title={product.title}
                        productImageFile={product.productImageFile}
                        onOpenDetail={NOOP}
                        onRemove={() => onRemove(product.id)}
                    />
                ))}
            </div>
        </div>
    );
}

export default AddedProductList;