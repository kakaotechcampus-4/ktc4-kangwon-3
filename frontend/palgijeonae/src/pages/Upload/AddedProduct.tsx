import urlIcon from "../../assets/upload-url.svg"
import imageIcon from "../../assets/upload-img_txt.svg"
import DefaultBox from "../../components/common/DefaultBox/index.tsx";
import toggleIcon from "../../assets/upload-toggle.svg"
import defaultThumbnail from "../../assets/upload-defaultThumbnail.svg"

interface AddedProductProps {
    type: "url" | "text/image";
    title: string;
    thumbnail?: string;
}


function AddedProduct({ type, title, thumbnail }: AddedProductProps) {
    return ( 
        <DefaultBox>
            <div className="relative flex w-full gap-5">
                <img src={thumbnail ? thumbnail : defaultThumbnail} 
                    alt="상품 썸네일" 
                    className="w-20 h-20 object-cover rounded-lg border border-neutral-border" />
                <div className="flex flex-col gap-3">
                    <div className="flex gap-2 items-center">
                        <img src={type === "url" ? urlIcon : imageIcon} 
                            alt={type === "url" ? "URL 아이콘" : "이미지 아이콘"}
                            className="w-5 h-5" />
                        <p className="text-base text-neutral-border font-bold">{type === "url" ? "URL" : "이미지 / 텍스트"}</p>
                    </div>
                    <h3 className="text-xl font-bold text-neutral-dark">{title}</h3>
                </div>
                <img src={toggleIcon} alt="토글 아이콘" className="absolute top-1/2 right-0 h-5 w-5 -translate-y-1/2" />
            </div>
        </DefaultBox>
     );
}

export default AddedProduct;