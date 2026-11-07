import { type ClipboardEvent, type DragEvent, useRef } from "react";

import uploadInputIcon from "@/assets/upload-inputImage.png";
import Button from "@/components/common/Button";
import HelpTooltip from "@/components/common/HelpTooltip";
import { ALLOWED_IMAGE_EXTENSIONS_LABEL, MAX_FILE_SIZE_MB } from "@/pages/Upload/constants.ts";
import { isAllowedImageType, isWithinFileSizeLimit } from "@/pages/Upload/utils/validation.ts";

interface ImageUploadFieldProps {
    id: string
    title: string
    description: string
    multiple?: boolean
    isOption?: boolean
    optionLabel?: string
    helperText?: string
    countLabel?: string
    tooltip?: string
    onChange: (files: File[]) => void
}

function ImageUploadField({ id, title, description, multiple = false, isOption = false, optionLabel = "선택", helperText, countLabel, tooltip, onChange }: ImageUploadFieldProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFiles = (fileList: FileList | null) => {
        if (!fileList) {
            return;
        }
        const files = Array.from(fileList);
        const hasInvalidType = files.some((file) => !isAllowedImageType(file));
        const hasOversizedFile = files.some((file) => !isWithinFileSizeLimit(file));
        const validFiles = files.filter((file) => isAllowedImageType(file) && isWithinFileSizeLimit(file));

        if (hasInvalidType) {
            alert(`${ALLOWED_IMAGE_EXTENSIONS_LABEL} 형식의 이미지만 첨부할 수 있습니다.`);
        }

        if (hasOversizedFile) {
            alert(`이미지는 1장당 ${MAX_FILE_SIZE_MB}MB까지만 첨부할 수 있습니다.`);
        }

        if (validFiles.length === 0) {
            return;
        }

        onChange(multiple ? validFiles : validFiles.slice(0, 1));
    };

    const handleDrop = (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        handleFiles(event.dataTransfer.files);
    };

    // Ctrl+V / Cmd+V로 붙여넣은 클립보드의 파일(캡처 이미지 등)을 업로드와 같은 검증으로 처리한다. 
    const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
        if (event.clipboardData.files.length === 0) {
            return;
        }
        event.preventDefault();
        handleFiles(event.clipboardData.files);
    };

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center justify-between gap-3.75">
                <div className="flex items-center gap-3.75">
                    <h3 className="text-xl leading-6 font-semibold text-black">{title}</h3>
                    {isOption && <span className="text-xs leading-3.5 text-neutral-border">{optionLabel}</span>}
                    {tooltip && <HelpTooltip label={`${title} 설명`} className="max-w-sm">{tooltip}</HelpTooltip>}
                </div>
                {countLabel && <span className="text-xs leading-3.5 text-neutral-border">{countLabel}</span>}
            </div>
            {helperText && <p className="text-sm font-light text-neutral-border">{helperText}</p>}

            {/* 영역을 클릭하면 선택(포커스)만 되고, 선택된 상태에서 Ctrl+V로 붙여넣을 수 있다. 파일 선택창은 안의 버튼으로 연다. */}
            <div
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
                onPaste={handlePaste}
                tabIndex={0}
                className="flex w-full items-center gap-6 rounded-[10px] border border-dashed border-neutral-border py-6.5 px-4.75 focus-within:border-solid focus-within:border-black focus-within:ring-1 focus-within:ring-black"
            >
                <input
                    ref={fileInputRef}
                    id={id}
                    type="file"
                    accept="image/*"
                    multiple={multiple}
                    className="hidden"
                    onChange={(event) => handleFiles(event.target.files)}
                />

                <div className="flex h-17.5 w-17.5 shrink-0 items-center justify-center rounded-[10px] bg-[#E7EEFB]">
                    <img src={uploadInputIcon} alt="" className="h-12.5 w-12.5 object-contain" />
                </div>

                <div className="flex flex-col gap-3.5">
                    <p className="text-base leading-4.75 font-semibold text-black">
                        {description}
                    </p>
                    <p className="text-sm leading-4.25 font-light text-neutral-border">
                        이 영역에 이미지 파일을 끌어다 놓거나, 영역을 클릭한 뒤 붙여넣을 수 있어요.
                    </p>
                </div>

                <div className="ml-auto shrink-0">
                    <Button text="파일 선택" variant="secondary" fontSize={14} onClick={() => fileInputRef.current?.click()} />
                </div>
            </div>
        </div>
    );
}

export default ImageUploadField;
