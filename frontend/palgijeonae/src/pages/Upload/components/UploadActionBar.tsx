import { useMemo } from "react";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
import BottomActionBar from "@/components/common/BottomActionBar";
import Button from "@/components/common/Button/index.tsx";
import { MAX_PRODUCT_COUNT } from "@/pages/Upload/constants.ts";
import { useObjectUrls } from "@/pages/Upload/hooks/useObjectUrls.ts";
import type { Product } from "@/pages/Upload/types.ts";

const NO_FILES: File[] = [];
const MAX_THUMBNAILS = 3;

function BarThumbnail({ file }: { file?: File }) {
    const files = useMemo(() => (file ? [file] : NO_FILES), [file]);
    const [url] = useObjectUrls(files);

    return <img src={url ? url : defaultThumbnail} alt="" className="-ml-3 size-8 shrink-0 rounded-lg border-2 border-white object-cover first:ml-0" />;
}

interface UploadActionBarProps {
    products: Product[]
    onStart: () => void
    // 확인할 제품 패널로 스크롤한다. 패널이 본문 아래에 있는 화면 크기에서만 보인다.
    onShowList: () => void
}

/** 업로드 화면 하단 바. 담은 상품 수를 보여주고 진단을 시작한다. */
function UploadActionBar({ products, onStart, onShowList }: UploadActionBarProps) {
    return (
        <BottomActionBar
            actions={
                <>
                    <Button text="목록 보기" onClick={onShowList} variant="secondary" fontSize={15} className="hidden self-center md:flex xl:hidden" />
                    <Button text="진단 시작하기" onClick={onStart} fontSize={15} className="self-center" />
                </>
            }
        >
            <div className="hidden items-center md:flex">
                {products.slice(0, MAX_THUMBNAILS).map((product) => (
                    <BarThumbnail key={product.id} file={product.productImageFile} />
                ))}
            </div>
            <p className="text-sm font-bold text-black md:text-base">
                확인할 제품 <span className="text-primary">{products.length} / {MAX_PRODUCT_COUNT}</span>
            </p>
        </BottomActionBar>
    );
}

export default UploadActionBar;
