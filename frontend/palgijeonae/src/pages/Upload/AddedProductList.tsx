import SectionIntro from "../../components/common/SectionIntro/index.tsx";
import AddedProduct from "./AddedProduct.tsx";
import type { Product } from "./types.ts";

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
                        thumbnail={product.thumbnail}
                        onRemove={() => onRemove(product.id)}
                    />
                ))}
            </div>
        </div>
    );
}

export default AddedProductList;