import { SourceType } from "@/api/types/common";
import Button from "@/components/common/Button";
import DefaultBox from "@/components/common/DefaultBox";
import HelpTooltip from "@/components/common/HelpTooltip";
import PreviewFrame from "@/components/common/PreviewFrame";
import { NOOP, PREVIEW_PRODUCTS } from "@/pages/Main/constants";
import AddedProduct from "@/pages/Upload/components/AddedProduct";
import FormField from "@/pages/Upload/components/FormField";
import ImageUploadField from "@/pages/Upload/components/ImageUploadField";
import InputTypeTabs from "@/pages/Upload/components/InputTypeTabs";
import { MAX_PRODUCT_IMAGE_COUNT, MAX_PRODUCT_NAME_LENGTH } from "@/pages/Upload/constants";

/** 사용 방법 1단계 미리보기: 텍스트·이미지로 상품을 담는 화면. */
function UploadStepPreview() {
    return (
        <PreviewFrame label="상품 담기 화면 미리보기" baseWidth={650}>
            <div className="flex w-full flex-col gap-8">
                <DefaultBox align="left">
                    <InputTypeTabs selected={SourceType.TextImage} onSelect={NOOP} />
                    <FormField
                        id="preview-step-upload-product-name"
                        title="제품명"
                        placeholder=""
                        value={PREVIEW_PRODUCTS.slipperAwaiting.productName}
                        onChange={NOOP}
                        maxLength={MAX_PRODUCT_NAME_LENGTH}
                    />
                    <FormField
                        id="preview-step-upload-content"
                        title="제품 상세페이지 내용"
                        placeholder=""
                        variant="textarea"
                        value={PREVIEW_PRODUCTS.slipperAwaiting.sourceText ?? ""}
                        onChange={NOOP}
                    />
                    <ImageUploadField
                        id="preview-step-upload-content-images"
                        title="상세페이지 이미지"
                        description="상세 페이지를 캡처한 이미지를 첨부하세요."
                        multiple={true}
                        isOption={true}
                        optionLabel="보조 입력"
                        helperText="텍스트 입력을 보완하는 참고 자료예요. 이미지만으로는 제출할 수 없어요."
                        countLabel={`0/${MAX_PRODUCT_IMAGE_COUNT}`}
                        onChange={NOOP}
                    />
                    <ImageUploadField
                        id="preview-step-upload-image"
                        title="제품 대표 사진"
                        description="제품을 구분할 대표 사진을 첨부하세요."
                        isOption={true}
                        onChange={NOOP}
                    />
                    <div className="flex w-full flex-col items-stretch gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="flex min-w-0 items-center gap-2">
                            <HelpTooltip label="입력 방법 추가 설명">
                                분석을 위해 필요한 정보가 상세페이지에 충분히 포함되어 있는지 확인하세요.
                            </HelpTooltip>
                            <p className="text-sm text-neutral-dark md:truncate">상세페이지 본문을 텍스트로 입력하세요. 상세페이지 이미지는 선택 사항입니다.</p>
                        </div>
                        <div className="shrink-0">
                            <Button text="상품 추가하기" onClick={NOOP} fontSize={15} className="w-full md:w-auto" />
                        </div>
                    </div>
                </DefaultBox>
                <AddedProduct
                    type={SourceType.Url}
                    title={PREVIEW_PRODUCTS.earphoneResult.productName}
                    onOpenDetail={NOOP}
                    onRemove={NOOP}
                />
            </div>
        </PreviewFrame>
    );
}

export default UploadStepPreview;
