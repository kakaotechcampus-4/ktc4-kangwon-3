interface SectionIntroProps {
    title: string
    description?: string
    size?: '3xl' | '2xl' | 'xl'
}

const TITLE_CLASSES: Record<NonNullable<SectionIntroProps['size']>, string> = {
    '3xl': 'text-3xl leading-12 font-bold',
    '2xl': 'text-2xl leading-9 font-bold',
    'xl': 'text-xl leading-6 font-semibold',
}

function SectionIntro({ title, description, size = '3xl' }: SectionIntroProps) {
    return (
        <div className="flex flex-col items-start gap-2">
            <div className={`${TITLE_CLASSES[size]} text-black`}>{title}</div>
            {description && <p className="whitespace-pre-line text-xl leading-8.75 text-neutral-text">{description}</p>}
        </div>
    );
}

export default SectionIntro;
