interface FormFieldProps {
    id: string
    title: string
    placeholder: string
    variant?: 'input' | 'textarea'
    value: string
    onChange: (value: string) => void
    // 백엔드 요청 스키마의 길이 제한(예: productName [0, 100])을 표시/적용하기 위한 값. 없으면 제한 없음.
    maxLength?: number
}

const FIELD_CLASSES =
    "box-border w-full rounded-[10px] border border-neutral-border px-4.75 text-sm text-black placeholder:font-light placeholder:text-neutral-border";

function FormField({ id, title, placeholder, variant = 'input', value, onChange, maxLength }: FormFieldProps) {
    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center justify-between">
                <label className="text-xl leading-6 font-semibold text-black" htmlFor={id}>{title}</label>
                {maxLength !== undefined && (
                    <span className="text-sm text-neutral-border">{value.length}/{maxLength}</span>
                )}
            </div>
            {variant === 'textarea' ? (
                <textarea
                    id={id}
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    maxLength={maxLength}
                    className={`${FIELD_CLASSES} min-h-35 py-2`}
                />
            ) : (
                <input
                    id={id}
                    type="text"
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    maxLength={maxLength}
                    className={`${FIELD_CLASSES} h-13`}
                />
            )}
        </div>
    );
}

export default FormField;
