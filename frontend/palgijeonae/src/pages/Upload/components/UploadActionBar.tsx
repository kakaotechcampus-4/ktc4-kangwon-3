import { useEffect, useMemo } from "react";

import defaultThumbnail from "@/assets/upload-defaultThumbnail.svg"
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

/** 화면 아래에 고정된 바. 담은 상품 수를 보여주고 진단을 시작한다. */
function UploadActionBar({ products, onStart, onShowList }: UploadActionBarProps) {
    // 바가 화면 아래를 덮는 만큼 페이지 맨 아래(푸터)가 가려지지 않도록, Layout이 읽는 여백 값을 정한다.
    useEffect(() => {
        document.documentElement.style.setProperty("--action-bar-space", "calc(5rem + env(safe-area-inset-bottom))");
        return () => {
            document.documentElement.style.removeProperty("--action-bar-space");
        };
    }, []);

    return (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-neutral-line bg-white pb-[env(safe-area-inset-bottom)]">
            {/* 안쪽 폭은 Layout의 main 폭과 같게 맞춘다. */}
            <div className="mx-auto flex w-full max-w-297 items-center justify-between gap-3 px-5 py-3 md:w-3/5 md:min-w-150 md:px-0 md:py-4">
                <div className="flex min-w-0 items-center gap-3">
                    <div className="hidden items-center md:flex">
                        {products.slice(0, MAX_THUMBNAILS).map((product) => (
                            <BarThumbnail key={product.id} file={product.productImageFile} />
                        ))}
                    </div>
                    <p className="text-sm font-bold text-black md:text-base">
                        확인할 제품 <span className="text-primary">{products.length} / {MAX_PRODUCT_COUNT}</span>
                    </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                    <Button text="목록 보기" onClick={onShowList} variant="secondary" fontSize={15} className="hidden self-center md:flex xl:hidden" />
                    <Button text="진단 시작하기" onClick={onStart} fontSize={15} className="self-center" />
                </div>
            </div>
        </div>
    );
}

export default UploadActionBar;
