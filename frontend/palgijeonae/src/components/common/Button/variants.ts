import { cva } from "class-variance-authority";

export const buttonVariants = cva(
    // disabled는 variant별 전용 색을 쓰고, aria-disabled는 원래 색을 유지한 채 투명도만 낮춘다.
    "flex cursor-pointer items-center justify-center gap-2.5 self-start rounded-xl leading-[1.2] text-center transition-[background-color,border-color,box-shadow] duration-150 outline-none focus-visible:ring-3 focus-visible:ring-primary/25 disabled:cursor-default aria-disabled:cursor-default aria-disabled:opacity-35",
    {
        variants: {
            variant: {
                // 핵심 액션
                primary:
                    "bg-primary px-6.25 py-3.5 font-bold text-white shadow-button-primary enabled:not-aria-disabled:hover:bg-primary-hover enabled:not-aria-disabled:hover:shadow-button-primary-hover enabled:not-aria-disabled:active:bg-primary-active enabled:not-aria-disabled:active:shadow-none disabled:bg-button-disabled-bg disabled:text-button-disabled-text disabled:shadow-none",
                // 보조 액션
                secondary:
                    "border border-box-line bg-white px-6 py-3.25 font-semibold text-neutral-text shadow-button-secondary enabled:not-aria-disabled:hover:border-button-line-hover enabled:not-aria-disabled:hover:bg-button-hover-bg enabled:not-aria-disabled:active:bg-button-active-bg enabled:not-aria-disabled:active:shadow-none focus-visible:border-primary disabled:border-neutral-line disabled:bg-button-hover-bg disabled:text-button-disabled-text disabled:shadow-none",
            },
            // 폼 안의 인라인 액션처럼 화면에서 덜 두드러져야 할 때 작게 쓴다.
            size: {
                md: "",
                sm: "rounded-lg",
            },
        },
        compoundVariants: [
            // 패딩은 variant 값을 덮어써야 해서 compound로 둔다. secondary는 테두리 1px만큼 패딩을 줄여 높이를 맞춘다.
            { variant: "primary", size: "sm", class: "px-4 py-2 font-semibold" },
            { variant: "secondary", size: "sm", class: "px-3.75 py-1.75" },
        ],
        defaultVariants: {
            variant: "primary",
            size: "md",
        },
    },
);
