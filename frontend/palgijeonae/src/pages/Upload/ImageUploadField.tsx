import { type DragEvent } from "react";

import uploadInputIcon from "@/assets/upload-inputImage.png";

interface ImageUploadFieldProps {
    id: string
    title: string
    description: string
    multiple?: boolean
    isOption?: boolean
    countLabel?: string
    onChange: (files: File[]) => void
}

// 백엔드 presigned URL 발급이 jpg, jpeg, png, webp 확장자만 허용하므로 동일하게 제한한다.
// accept 속성은 파일 선택창 필터일 뿐이라 드래그앤드롭에는 적용되지 않아, 여기서 한 번 더 검증한다.
const ALLOWED_MIME_TYPES = ["image/jpeg", "image/jpg", "image/png", "image/webp"];

function ImageUploadField({ id, title, description, multiple = false, isOption = false, countLabel, onChange }: ImageUploadFieldProps) {
    const handleFiles = (fileList: FileList | null) => {
        if (!fileList) {
            return;
        }
        const files = Array.from(fileList);
        const validFiles = files.filter((file) => ALLOWED_MIME_TYPES.includes(file.type));

        if (validFiles.length < files.length) {
            alert("jpg, jpeg, png, webp 형식의 이미지만 첨부할 수 있습니다.");
        }

        if (validFiles.length === 0) {
            return;
        }

        onChange(multiple ? validFiles : validFiles.slice(0, 1));
    };

    const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
        event.preventDefault();
        handleFiles(event.dataTransfer.files);
    };

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center gap-3.75">
                <h3 className="text-xl leading-6 font-semibold text-black">{title}</h3>
                {isOption && <span className="text-xs leading-3.5 text-neutral-border">선택</span>}
                {countLabel && <span className="text-xs leading-3.5 text-neutral-border">{countLabel}</span>}
            </div>

            <label
                htmlFor={id}
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
                className="flex w-full cursor-pointer items-center gap-6 rounded-[10px] border border-dashed border-neutral-border py-6.5 px-4.75"
            >
                <input
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
                        또는 이 영역에 이미지 파일을 끌어다 놓으세요.
                    </p>
                </div>
            </label>
        </div>
    );
}

export default ImageUploadField;
