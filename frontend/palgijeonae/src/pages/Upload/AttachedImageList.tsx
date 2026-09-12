import { useEffect, useMemo } from "react";

interface AttachedImageListProps {
    files: File[]
}

function AttachedImageList({ files }: AttachedImageListProps) {
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
            <h3 className="text-xl leading-6 font-semibold text-black">첨부된 이미지</h3>
            <div className="flex w-full flex-wrap gap-4">
                {files.map((file, index) => (
                    <img
                        key={`${file.name}-${index}`}
                        src={previewUrls[index]}
                        alt={file.name}
                        className="h-40 w-60 rounded-2xl object-cover"
                    />
                ))}
            </div>
        </div>
    );
}

export default AttachedImageList;
