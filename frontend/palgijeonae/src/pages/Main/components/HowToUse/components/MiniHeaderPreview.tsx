import logo from "@/assets/logo.svg";
import { useIsMobile } from "@/hooks/useIsMobile";

/** 눌러야 할 곳을 보여주는 축소 헤더. 데스크톱은 로고 옆 메뉴 글자 중 「진단 결과」, 모바일은 우측 상단 햄버거 버튼을 강조한다. 실제 Header는 로그인 상태와 내 정보에 따라 모양이 바뀌므로 재사용하지 않고 전용 미리보기를 둔다. */
function MiniHeaderPreview() {
    const isMobile = useIsMobile();

    return (
        <div className="flex w-full items-center justify-between gap-2 rounded-lg border border-box-line bg-white px-8 py-4">
            <div className="flex items-center gap-5">
                <img src={logo} alt="사이트 로고" className="h-5 w-auto object-contain" />
                {!isMobile && (
                    <div className="flex items-center gap-3 text-xs text-neutral-text">
                        <span className="font-medium">홈</span>
                        <span className="font-medium">상품 진단</span>
                        <span className="rounded-md px-1.5 py-0.5 font-bold text-primary ring-4 ring-primary/20">진단 결과</span>
                    </div>
                )}
            </div>
            {isMobile && (
                <span className="flex size-9 items-center justify-center rounded-lg bg-white text-neutral-text ring-4 ring-primary/20">
                    <svg aria-hidden viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <path d="M4 7h16M4 12h16M4 17h16" />
                    </svg>
                </span>
            )}
        </div>
    );
}

export default MiniHeaderPreview;
