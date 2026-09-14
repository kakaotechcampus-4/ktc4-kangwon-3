import urlIcon from "../../assets/upload-url.svg"
import imageIcon from "../../assets/upload-img_txt.svg"

interface AddedProductProps {
    type: "url" | "text/image";
    title: string;
    thumbnail?: string;
}


function AddedProduct({ type, title, thumbnail }: AddedProductProps) {
    return ( 
        <div className="flex w-full px-2 py-2 gap-4 border border-neutral-border rounded-lg">
            <img src={thumbnail ? thumbnail : "/default-thumbnail.png"} alt="상품 썸네일" />
            <div className="flex flex-col gap-2">
                <div className="flex flex-col gap-1">
                    <img src={type === "url" ? urlIcon : imageIcon} alt={type === "url" ? "URL 아이콘" : "이미지 아이콘"} />
                    <p>{type === "url" ? "URL" : "이미지 / 텍스트"}</p>
                </div>
                <h3>{title}</h3>
            </div>
        </div>
     );
}

export default AddedProduct;