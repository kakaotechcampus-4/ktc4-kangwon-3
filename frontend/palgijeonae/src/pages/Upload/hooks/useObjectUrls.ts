import { useEffect, useState } from "react";

/** File 목록의 미리보기 주소(blob URL)를 만들고, 목록이 바뀌거나 화면이 사라지면 해제한다. files는 값이 바뀔 때만 새 배열이어야 한다. */
export function useObjectUrls(files: File[]): string[] {
    const [urls, setUrls] = useState<string[]>([]);

    useEffect(() => {
        const created = files.map((file) => URL.createObjectURL(file));
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setUrls(created);
        return () => {
            created.forEach((url) => URL.revokeObjectURL(url));
        };
    }, [files]);

    return urls;
}
