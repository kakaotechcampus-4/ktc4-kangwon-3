import Toggle from "@/components/common/Toggle/index.tsx";

interface SettingToggleRowProps {
    title: string
    description?: string
    checked: boolean
    onChange: (checked: boolean) => void
    disabled?: boolean
}

function SettingToggleRow({ title, description, checked, onChange, disabled }: SettingToggleRowProps) {
    return (
        <div className="relative w-full">
            <h6>{title}</h6>
            {description && <p>{description}</p>}
            <Toggle
                checked={checked}
                onChange={onChange}
                disabled={disabled}
                className="absolute right-0 top-1/2 -translate-y-1/2"
            />
        </div>
    );
}

export default SettingToggleRow;
