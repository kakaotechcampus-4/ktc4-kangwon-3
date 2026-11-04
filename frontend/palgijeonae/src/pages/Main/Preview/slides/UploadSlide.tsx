import { SourceType } from "@/api/types";
import Button from "@/components/common/Button";
import DefaultBox from "@/components/common/DefaultBox";
import HelpTooltip from "@/components/common/HelpTooltip";
import PreviewFrame from "@/components/common/PreviewFrame";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/previewMocks";
import AddedProduct from "@/pages/Upload/AddedProduct";
import { MAX_PRODUCT_NAME_LENGTH } from "@/pages/Upload/constraints";
import FormField from "@/pages/Upload/form/FormField";
import ImageUploadField from "@/pages/Upload/form/ImageUploadField";
import InputTypeTabs from "@/pages/Upload/InputTypeTabs";

/** 메인 페이지 미리보기: 상품 업로드 화면. */
function UploadSlide() {
    return (
        <PreviewFrame label="상품 업로드 화면 미리보기" baseWidth={864} maxHeight={520}>
            <div className="flex w-full flex-col gap-8">
                <DefaultBox align="left">
                    <InputTypeTabs selected={SourceType.Url} onSelect={NOOP} />
                    <FormField
                        id="preview-slide-upload-product-name"
                        title="제품명"
                        placeholder=""
                        value="블루투스 이어폰 TWS"
                        onChange={NOOP}
                        maxLength={MAX_PRODUCT_NAME_LENGTH}
                    />
                    <FormField
                        id="preview-slide-upload-link"
                        title="제품 상세페이지 링크"
                        placeholder=""
                        value={PREVIEW_PRODUCTS.earphoneResult.sourceUrl ?? ""}
                        onChange={NOOP}
                    />
                    <ImageUploadField
                        id="preview-slide-upload-image"
                        title="제품 대표 사진"
                        description="제품을 구분할 대표 사진을 첨부하세요."
                        isOption={true}
                        onChange={NOOP}
                    />
                    <div className="flex w-full items-center justify-between gap-4">
                        <div className="flex min-w-0 items-center gap-2">
                            <HelpTooltip label="입력 방법 추가 설명">
                                일부 링크는 AI가 접근하기 어려울 수 있습니다. 실패 시 텍스트 / 이미지 입력을 사용해주세요.
                            </HelpTooltip>
                            <p className="truncate text-sm text-neutral-dark">상세정보가 포함된 판매할 제품의 링크를 첨부하세요.</p>
                        </div>
                        <Button text="상품 추가하기" onClick={NOOP} fontSize={15} />
                    </div>
                </DefaultBox>
                <AddedProduct type={SourceType.TextImage} title={PREVIEW_PRODUCTS.slipperAwaiting.productName} onRemove={NOOP} />
            </div>
        </PreviewFrame>
    );
}

export default UploadSlide;
