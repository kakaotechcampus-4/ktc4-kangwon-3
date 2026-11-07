import { SourceType } from "@/api/types/common.ts"
import { cn } from "@/lib/cn";

const INPUT_TYPE_TABS = [
    { key: SourceType.Url, label: "URL" },
    { key: SourceType.TextImage, label: "텍스트 / 이미지" },
] as const;

export type InputType = typeof INPUT_TYPE_TABS[number]["key"];

interface InputTypeTabsProps {
    selected: InputType
    onSelect: (type: InputType) => void
}

function InputTypeTabs({ selected, onSelect }: InputTypeTabsProps) {
    return (
        <div className="flex flex-row w-full gap-4">
            {INPUT_TYPE_TABS.map(({ key, label }) => (
                <button
                    key={key}
                    type="button"
                    onClick={() => onSelect(key)}
                    className={cn(
                        "flex cursor-pointer items-center justify-center rounded-lg border px-6 py-2 text-base font-medium",
                        selected === key ? "border-neutral-border" : "border-transparent",
                    )}
                >
                    {label}
                </button>
            ))}
        </div>
    );
}

export default InputTypeTabs;
