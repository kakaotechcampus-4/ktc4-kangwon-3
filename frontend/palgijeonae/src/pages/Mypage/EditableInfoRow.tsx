import { useId, useState } from "react";

import Button from "@/components/common/Button/index.tsx";
import { cn } from "@/lib/cn";

interface EditableInfoRowProps {
    title: string
    description: string
    editable?: boolean
    maxLength: number
    onChange: (value: string) => void
    disabled?: boolean
    onSave: () => void
}

/** 프로필에서 쓰이는 정보 행 하나. editable이면 수정 버튼으로 같은 자리에서 인라인 편집으로 바뀐다. */
function EditableInfoRow({ title, description, editable = false, maxLength, onChange, disabled = false, onSave }: EditableInfoRowProps) {
    const inputId = useId();
    const [isEditing, setIsEditing] = useState(false);
    const [draftValue, setDraftValue] = useState(description);

    // 저장이 성공해 description(서버 반영 값)이 바뀌면 편집을 종료한다.
    const [syncedDescription, setSyncedDescription] = useState(description);
    if (description !== syncedDescription) {
        setSyncedDescription(description);
        setIsEditing(false);
        setDraftValue(description);
    }

    const startEditing = () => {
        setDraftValue(description);
        setIsEditing(true);
    };

    const cancelEditing = () => {
        setIsEditing(false);
        setDraftValue(description);
    };

    const handleChange = (value: string) => {
        setDraftValue(value);
        onChange(value);
    };

    const trimmedLength = draftValue.trim().length;
    const isInvalid = trimmedLength === 0 || trimmedLength > maxLength;

    const handleSave = () => {
        // 값이 그대로면 요청 없이 편집만 종료한다.
        if (draftValue.trim() === description.trim()) {
            setIsEditing(false);
            return;
        }
        onSave();
    };

    if (!isEditing) {
        return (
            <div className="flex w-full items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <span className="w-16 shrink-0 text-sm font-semibold text-neutral-label">{title}</span>
                    <span className="text-base text-black">{description}</span>
                </div>
                {editable && (
                    <button
                        type="button"
                        onClick={startEditing}
                        className="shrink-0 cursor-pointer rounded-full border border-neutral-border px-3 py-1 text-sm font-semibold text-neutral-dark"
                    >
                        {title} 수정
                    </button>
                )}
            </div>
        );
    }

    return (
        <div className="flex w-full items-center gap-3">
            <label htmlFor={inputId} className="w-16 shrink-0 text-sm font-semibold text-neutral-label">{title}</label>
            <div className="flex flex-1 items-center gap-2">
                <input
                    id={inputId}
                    autoFocus
                    value={draftValue}
                    disabled={disabled}
                    onChange={(event) => handleChange(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === "Escape") {
                            cancelEditing();
                        }
                    }}
                    className="h-10 w-full rounded-lg border border-neutral-border px-3 text-base text-black disabled:opacity-50"
                />
                <span className={cn("shrink-0 text-xs", trimmedLength > maxLength ? "text-status-danger" : "text-neutral-border")}>
                    {trimmedLength}/{maxLength}
                </span>
            </div>
            <Button text="취소" variant="secondary" fontSize={14} onClick={cancelEditing} disabled={disabled} />
            <Button text="저장" fontSize={14} onClick={handleSave} disabled={disabled || isInvalid} />
        </div>
    );
}

export default EditableInfoRow;
