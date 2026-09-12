import { useEffect, useMemo, type DragEvent } from "react";

import uploadInputIcon from "../../assets/upload-inputImage.png";

interface ImageUploadFieldProps {
    id: string
    title: string
    file: File | null
    isOption?: boolean
    onChange: (file: File | null) => void
}

function ImageUploadField({ id, title, file, isOption = false, onChange }: ImageUploadFieldProps) {
    const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

    useEffect(() => {
        return () => {
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
            }
        };
    }, [previewUrl]);

    const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
        event.preventDefault();
        const droppedFile = event.dataTransfer.files?.[0];
        if (droppedFile) {
            onChange(droppedFile);
        }
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
                    className="hidden"
                    onChange={(event) => onChange(event.target.files?.[0] ?? null)}
                />

                <div className="flex h-17.5 w-17.5 shrink-0 items-center justify-center rounded-[10px] bg-[#E7EEFB]">
                    {previewUrl ? (
                        <img
                            src={previewUrl}
                            alt={title}
                            className="h-full w-full rounded-[10px] object-cover"
                        />
                    ) : (
                        <img src={uploadInputIcon} alt="" className="h-12.5 w-12.5 object-contain" />
                    )}
                </div>

                <div className="flex flex-col gap-3.5">
                    <p className="text-base leading-4.75 font-semibold text-black">
                        {file ? file.name : "제품을 구분할 대표 사진을 첨부하세요."}
                    </p>
                    <p className="text-sm leading-4.25 font-light text-neutral-border">
                        {file
                            ? "다른 이미지를 선택하려면 클릭하거나 끌어다 놓으세요."
                            : "또는 이 영역에 이미지 파일을 끌어다 놓으세요."}
                    </p>
                </div>
            </label>
        </div>
    );
}

export default ImageUploadField;
