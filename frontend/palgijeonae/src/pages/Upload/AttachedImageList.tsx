import { useEffect, useMemo } from "react";

interface AttachedImageListProps {
    title: string
    files: File[]
}

function AttachedImageList({ title, files }: AttachedImageListProps) {
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
                    <img
                        key={`${file.name}-${index}`}
                        src={previewUrls[index]}
                        alt={file.name}
                        className="h-39 w-39 rounded-2xl object-cover"
                    />
                ))}
            </div>
        </div>
    );
}

export default AttachedImageList;
