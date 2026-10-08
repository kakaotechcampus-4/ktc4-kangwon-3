import { countGraphemes, truncateGraphemes, truncateToCodeUnitLength } from "@/lib/text";

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
        // 최대 길이 제한이 없다면 바로 반영한다.
        if (maxLength === undefined) {
            onChange(newValue);
            return;
        }
        // textarea : 제품 설명에 쓰이는 type. 코드 유닛 기준으로 자른다.
        // input : 제품명 / link에 쓰이는 type. 보이는 글자 수(grapheme) 기준으로 자른다. link는 이모지를 포함하지 않으므로 grapheme와 코드 유닛 기준 길이가 동일.
        onChange(variant === 'textarea' ? truncateToCodeUnitLength(newValue, maxLength) : truncateGraphemes(newValue, maxLength));
    };

    return (
        <div className="flex w-full flex-col items-start gap-3.5">
            <div className="flex w-full items-center gap-3.75">
                <label className="text-xl leading-6 font-semibold text-black" htmlFor={id}>{title}</label>
                {maxLength !== undefined && (
                    <span className="text-xs leading-3.5 text-neutral-border">{variant === 'textarea' ? value.length : countGraphemes(value)}/{maxLength}</span>
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
                    className={`${FIELD_CLASSES} h-13`}
                />
            )}
        </div>
    );
}

export default FormField;
