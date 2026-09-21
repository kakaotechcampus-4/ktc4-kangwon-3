import DefaultBox from "@/components/common/DefaultBox";

import type { ProductInputType, ResultStatus } from "./types.ts";

interface MyProductProps {
    title: string
    thumbnail?: string
    inputType: ProductInputType
    resultStatus: ResultStatus
    link?: string
    content?: string
    images?: string[]
}

function MyProduct(_props: MyProductProps) {
    return (
        <DefaultBox>
            상품 카드
        </DefaultBox>
    );
}

export default MyProduct;
