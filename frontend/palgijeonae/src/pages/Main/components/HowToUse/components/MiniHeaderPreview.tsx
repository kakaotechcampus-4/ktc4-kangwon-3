import logo from "@/assets/logo.png";
import { useIsMobile } from "@/hooks/useIsMobile";

/** 화면 우측 상단에서 눌러야 할 곳을 보여주는 축소 헤더. 데스크톱은 프로필 칩, 모바일은 햄버거 버튼을 강조한다. 실제 Header는 로그인 상태와 내 정보에 따라 모양이 바뀌므로 재사용하지 않고 전용 미리보기를 둔다. */
function MiniHeaderPreview() {
    const isMobile = useIsMobile();

    return (
        <div className="flex w-full items-center justify-between gap-2 rounded-lg border border-box-line bg-white px-8 py-4">
            <img src={logo} alt="사이트 로고" className="h-5 w-auto object-contain" />
            {isMobile ? (
                <span className="flex size-9 items-center justify-center rounded-lg bg-white text-neutral-text ring-4 ring-primary/20">
                    <svg aria-hidden viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <path d="M4 7h16M4 12h16M4 17h16" />
                    </svg>
                </span>
            ) : (
                <span className="flex h-7.5 items-center gap-2 rounded-full border border-neutral-line bg-white py-1 pr-2.5 pl-1 ring-4 ring-primary/20">
                    <span className="grid size-5.5 shrink-0 place-items-center rounded-full bg-primary-soft text-xs font-bold text-primary">홍</span>
                    <span className="text-sm font-medium text-neutral-text">홍길동 님</span>
                    <svg aria-hidden viewBox="0 0 16 16" className="size-4 shrink-0 text-neutral-dark">
                        <path d="M4.5 6.5 8 10l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </span>
            )}
        </div>
    );
}

export default MiniHeaderPreview;
