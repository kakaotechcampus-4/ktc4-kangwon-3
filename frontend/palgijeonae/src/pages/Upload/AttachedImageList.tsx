import { useEffect, useMemo } from "react";

import deleteIcon from "../../assets/delete-gray.svg";

interface AttachedImageListProps {
    title: string
    files: File[]
    onRemove: (index: number) => void
}

function AttachedImageList({ title, files, onRemove }: AttachedImageListProps) {
    const previewUrls = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);

    useEffect(() => {
        return () => {
            previewUrls.forEach((url) => URL.revokeObjectURL(url));
        };
    }, [previewUrls]);

    if (files.length === 0) {
        return null;
    }

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <h3 className="text-xl leading-6 font-semibold text-black">{title}</h3>
            <div className="flex w-full flex-wrap gap-4">
                {files.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="relative h-39 w-39">
                        <img
                            src={previewUrls[index]}
                            alt={file.name}
                            className="h-full w-full rounded-2xl object-cover"
                        />
                        <button
                            type="button"
                            onClick={() => onRemove(index)}
                            className="absolute top-2 right-2 flex h-4 w-4 cursor-pointer items-center justify-center rounded-full bg-white"
                        >
                            <img src={deleteIcon} alt="삭제" className="h-full w-full" />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default AttachedImageList;
