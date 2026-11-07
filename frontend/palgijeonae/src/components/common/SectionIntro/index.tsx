import { cva, type VariantProps } from "class-variance-authority";

const titleVariants = cva("text-black", {
    variants: {
        size: {
            '3xl': 'text-[22px] leading-[30px] tracking-[-0.02em] font-bold md:text-3xl md:leading-10',
            '2xl': 'text-[19px] leading-[27px] tracking-[-0.015em] font-bold md:text-2xl md:leading-8',
            'xl': 'text-base leading-[23px] tracking-[-0.01em] font-semibold md:text-xl md:leading-7',
        },
    },
    defaultVariants: {
        size: '3xl',
    },
});

const descriptionVariants = cva("whitespace-pre-line text-neutral-muted", {
    variants: {
        size: {
            '3xl': 'text-[15px] leading-[23px] md:text-lg md:leading-7',
            '2xl': 'text-sm leading-[21px] md:text-base md:leading-[25px]',
            'xl': 'text-[13px] leading-[19px] md:text-sm md:leading-[21px]',
        },
    },
    defaultVariants: {
        size: '3xl',
    },
});

// 제목과 설명 사이 간격. 크기가 클수록 넓게 둔다.
const wrapperVariants = cva("flex flex-col items-start", {
    variants: {
        size: {
            '3xl': 'gap-2 md:gap-2.5',
            '2xl': 'gap-1.5 md:gap-2',
            'xl': 'gap-1',
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
    const Heading = size === '2xl' ? 'h2' : size === 'xl' ? 'h3' : 'h1';
    return (
        <div className={wrapperVariants({ size })}>
            <Heading className={titleVariants({ size })}>{title}</Heading>
            {description && <p className={descriptionVariants({ size })}>{description}</p>}
        </div>
    );
}

export default SectionIntro;
