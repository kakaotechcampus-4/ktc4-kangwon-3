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
        <div className="flex flex-row w-full gap-2 md:gap-4">
            {INPUT_TYPE_TABS.map(({ key, label }) => (
                <button
                    key={key}
                    type="button"
                    onClick={() => onSelect(key)}
                    className={cn(
                        "flex cursor-pointer items-center justify-center rounded-lg border px-5 py-2 text-base font-semibold transition-colors duration-150 outline-none focus-visible:ring-3 focus-visible:ring-primary/25 md:px-6",
                        selected === key
                            ? "border-primary bg-primary text-white"
                            : "border-box-line bg-button-active-bg text-neutral-muted hover:text-neutral-text",
                    )}
                >
                    {label}
                </button>
            ))}
        </div>
    );
}

export default InputTypeTabs;
