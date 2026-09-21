import MyProduct from "./MyProduct.tsx";
import type { MyProductItem } from "./types.ts";

interface MyProductListProps {
    products: MyProductItem[]
}

function MyProductList({ products }: MyProductListProps) {
    return (
        <div className="flex w-full flex-col gap-3.5">
            전체 상품
            {products.map((product) => (
                <MyProduct key={product.id} {...product} />
            ))}
        </div>
    );
}

export default MyProductList;
