interface FormFieldProps {
    id: string
    title: string
    placeholder: string
    variant?: 'input' | 'textarea'
    value: string
    onChange: (value: string) => void
}

const FIELD_CLASSES =
    "box-border w-full rounded-[10px] border border-neutral-border px-4.75 text-sm text-black placeholder:font-light placeholder:text-neutral-border";

function FormField({ id, title, placeholder, variant = 'input', value, onChange }: FormFieldProps) {
    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <label className="text-xl leading-6 font-semibold text-black" htmlFor={id}>{title}</label>
            {variant === 'textarea' ? (
                <textarea
                    id={id}
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={`${FIELD_CLASSES} min-h-35 py-2`}
                />
            ) : (
                <input
                    id={id}
                    type="text"
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={`${FIELD_CLASSES} h-13`}
                />
            )}
        </div>
    );
}

export default FormField;
