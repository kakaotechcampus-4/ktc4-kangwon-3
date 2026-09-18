import { cva, type VariantProps } from "class-variance-authority";

const titleVariants = cva("text-black", {
    variants: {
        size: {
            '3xl': 'text-3xl leading-12 font-bold',
            '2xl': 'text-2xl leading-9 font-bold',
            'xl': 'text-xl leading-6 font-semibold',
        },
    },
    defaultVariants: {
        size: '3xl',
    },
});

interface SectionIntroProps extends VariantProps<typeof titleVariants> {
    title: string
    description?: string
}

function SectionIntro({ title, description, size }: SectionIntroProps) {
    return (
        <div className="flex flex-col items-start gap-2">
            <div className={titleVariants({ size })}>{title}</div>
            {description && <p className="whitespace-pre-line text-xl leading-8.75 text-neutral-text">{description}</p>}
        </div>
    );
}

export default SectionIntro;
