import { type DragEvent } from "react";

import uploadInputIcon from "../../assets/upload-inputImage.png";

interface ImageUploadFieldProps {
    id: string
    title: string
    description: string
    multiple?: boolean
    isOption?: boolean
    onChange: (files: File[]) => void
}

function ImageUploadField({ id, title, description, multiple = false, isOption = false, onChange }: ImageUploadFieldProps) {
    const handleFiles = (fileList: FileList | null) => {
        if (!fileList) {
            return;
        }
        const files = Array.from(fileList);
        onChange(multiple ? files : files.slice(0, 1));
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
