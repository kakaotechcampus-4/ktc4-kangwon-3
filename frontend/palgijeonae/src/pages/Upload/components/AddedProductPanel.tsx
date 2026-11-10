import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import type { Product } from "@/pages/Upload/types.ts";

import AddedProduct from "./AddedProduct.tsx";

interface AddedProductPanelProps {
    products: Product[]
    onOpenDetail: (id: string) => void
    onRemove: (id: string) => void
}

function AddedProductPanel({ products, onOpenDetail, onRemove }: AddedProductPanelProps) {
    return (
        <DefaultBox className="gap-4 px-5 md:px-5">
            <SectionIntro title="확인할 제품" size="xl" />
            {products.length === 0 ? (
                <p className="text-sm text-neutral-border">아직 담은 제품이 없어요. 제품을 추가하면 여기에 보여요.</p>
            ) : (
                <>
                    <ul aria-label="확인할 제품 목록" className="flex w-full flex-col gap-2">
                        {products.map((product) => (
                            <li key={product.id}>
                                <AddedProduct
                                    type={product.type}
                                    title={product.title}
                                    productImageFile={product.productImageFile}
                                    onOpenDetail={() => onOpenDetail(product.id)}
                                    onRemove={() => onRemove(product.id)}
                                />
                            </li>
                        ))}
                    </ul>
                    <p className="text-xs text-neutral-border">항목을 누르면 입력 내용을 자세히 볼 수 있어요.</p>
                </>
            )}
        </DefaultBox>
    );
}

export default AddedProductPanel;
