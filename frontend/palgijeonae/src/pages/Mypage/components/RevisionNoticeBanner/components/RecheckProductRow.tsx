import type { RecheckProduct } from "@/api/lawAmendments.ts";

interface RecheckProductRowProps {
    product: RecheckProduct
    isPending: boolean
    onRediagnose: () => void
}

function RecheckProductRow({ product, isPending, onRediagnose }: RecheckProductRowProps) {
    return (
        <li className="flex items-center gap-3 py-2.5 md:gap-4 md:py-2">
            {/* 상품명은 누를 수 없는 텍스트다. 모바일에서는 2줄을 넘으면 말줄임한다. */}
            <p className="line-clamp-2 min-w-0 flex-1 text-[15px] leading-5.5 font-bold wrap-break-word text-neutral-text md:line-clamp-none">
                {product.productName}
            </p>
            <button
                type="button"
                onClick={onRediagnose}
                disabled={isPending}
                aria-label={`${product.productName} 재진단하기`}
                className="h-11 min-w-24 shrink-0 cursor-pointer rounded-full bg-status-notice px-4.5 text-[15px] font-bold whitespace-nowrap text-white outline-none focus-visible:ring-3 focus-visible:ring-status-notice/30 disabled:cursor-default disabled:opacity-55 md:h-9 md:min-w-22 md:px-4 md:text-sm"
            >
                {isPending ? (
                    <>
                        <span className="md:hidden">요청 중</span>
                        <span className="hidden md:inline">재진단 요청 중</span>
                    </>
                ) : (
                    "재진단하기"
                )}
            </button>
        </li>
    );
}

export default RecheckProductRow;
