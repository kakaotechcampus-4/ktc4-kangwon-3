import { cva, type VariantProps } from "class-variance-authority";

const titleVariants = cva("text-black", {
    variants: {
        size: {
            '3xl': 'text-[22px] leading-7.5 tracking-[-0.02em] font-bold md:text-3xl md:leading-10',
            '2xl': 'text-[19px] leading-6.75 tracking-[-0.015em] font-bold md:text-2xl md:leading-8',
            'xl': 'text-base leading-5.75 tracking-[-0.01em] font-semibold md:text-xl md:leading-7',
        },
    },
    defaultVariants: {
        size: '3xl',
    },
});

const descriptionVariants = cva("whitespace-pre-line text-neutral-muted", {
    variants: {
        size: {
            '3xl': 'text-[15px] leading-5.75 md:text-lg md:leading-7',
            '2xl': 'text-sm leading-5.25 md:text-base md:leading-6.25',
            'xl': 'text-[13px] leading-4.75 md:text-sm md:leading-5.25',
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
    // 제목 옆에 작은 회색 글씨로 붙는 보조 텍스트. 예: 전체 개수
    titleAside?: string
    description?: string
}

function SectionIntro({ title, titleAside, description, size }: SectionIntroProps) {
    const Heading = size === '2xl' ? 'h2' : size === 'xl' ? 'h3' : 'h1';
    const heading = <Heading className={titleVariants({ size })}>{title}</Heading>;
    return (
        <div className={wrapperVariants({ size })}>
            {titleAside ? (
                <div className="flex items-baseline gap-2">
                    {heading}
                    <span className="text-base font-medium text-neutral-border">{titleAside}</span>
                </div>
            ) : (
                heading
            )}
            {description && <p className={descriptionVariants({ size })}>{description}</p>}
        </div>
    );
}

export default SectionIntro;
