interface FormFieldProps {
    id: string
    title: string
    placeholder: string
    variant?: 'input' | 'textarea'
    value: string
    onChange: (value: string) => void
    maxLength?: number
}

const FIELD_CLASSES =
    "box-border w-full rounded-[10px] border border-neutral-border px-4.75 text-sm text-black placeholder:font-light placeholder:text-neutral-border";

function FormField({ id, title, placeholder, variant = 'input', value, onChange, maxLength }: FormFieldProps) {
    // 네이티브 maxLength는 한글 등 IME 조합 중에는 실시간으로 길이를 막지 못하므로 직접 잘라준다.
    const handleChange = (newValue: string) => {
        onChange(maxLength !== undefined ? newValue.slice(0, maxLength) : newValue);
    };

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center gap-3.75">
                <label className="text-xl leading-6 font-semibold text-black" htmlFor={id}>{title}</label>
                {maxLength !== undefined && (
                    <span className="text-xs leading-3.5 text-neutral-border">{value.length}/{maxLength}</span>
                )}
            </div>
            {variant === 'textarea' ? (
                <textarea
                    id={id}
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => handleChange(e.target.value)}
                    maxLength={maxLength}
                    className={`${FIELD_CLASSES} min-h-35 py-2`}
                />
            ) : (
                <input
                    id={id}
                    type="text"
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => handleChange(e.target.value)}
                    maxLength={maxLength}
                    className={`${FIELD_CLASSES} h-13`}
                />
            )}
        </div>
    );
}

export default FormField;
