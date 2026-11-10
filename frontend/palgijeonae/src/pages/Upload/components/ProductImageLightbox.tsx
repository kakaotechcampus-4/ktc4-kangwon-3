import ImageLightbox from "@/components/common/ImageLightbox";
import { useObjectUrls } from "@/pages/Upload/hooks/useObjectUrls.ts";

interface ProductImageLightboxProps {
    files: File[]
    currentIndex: number
    onIndexChange: (index: number) => void
    onClose: () => void
}

/** 상품의 상세페이지 이미지 File을 확대해서 보여주는 라이트박스. 삭제 버튼은 두지 않는다. */
function ProductImageLightbox({ files, currentIndex, onIndexChange, onClose }: ProductImageLightboxProps) {
    const urls = useObjectUrls(files);
    const images = files.map((file, index) => ({ src: urls[index], alt: file.name }));

    return <ImageLightbox images={images} currentIndex={currentIndex} onIndexChange={onIndexChange} onClose={onClose} />;
}

export default ProductImageLightbox;
