import SectionIntro from "@/components/common/SectionIntro/index.tsx";

import MyProduct from "./MyProduct.tsx";
import type { MyProductItem } from "./types.ts";

interface MyProductListProps {
    products: MyProductItem[]
}

function MyProductList({ products }: MyProductListProps) {
    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="전체 상품" size="xl" />
            <div className="flex w-full flex-col gap-3.5">
                {products.map((product) => (
                    <MyProduct key={product.id} {...product} />
                ))}
            </div>
        </div>
    );
}

export default MyProductList;
