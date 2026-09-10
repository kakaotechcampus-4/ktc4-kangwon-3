interface FormFieldProps {
    id: string
    title: string
    placeholder: string
    variant?: 'input' | 'textarea'
    value: string
    onChange: (value: string) => void
}

function FormField({ id, title, placeholder, variant = 'input', value, onChange }: FormFieldProps) {
    return (
        <div>
            <label htmlFor={id}>{title}</label>
            {variant === 'textarea' ? (
                <textarea
                    id={id}
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                />
            ) : (
                <input
                    id={id}
                    type="text"
                    placeholder={placeholder}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                />
            )}
        </div>
    );
}

export default FormField;
