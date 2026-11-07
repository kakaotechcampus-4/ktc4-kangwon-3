import logo from "@/assets/logo.png";

/** 화면 우측 상단 "마이페이지" 버튼 위치를 보여주는 축소 헤더. 실제 Header는 로그인 상태에 따라 버튼 라벨이 바뀌므로 재사용하지 않고, 마이페이지 pill을 항상 강조해 보여주는 전용 미리보기를 둔다. */
function MiniHeaderPreview() {
    return (
        <div className="flex w-full items-center justify-between gap-2 border border-box-line bg-white px-8 py-4 rounded-lg">
            <img src={logo} alt="사이트 로고" className="h-5 w-auto object-contain" />
            <span className="rounded-full bg-white px-3.5 py-1 text-xs font-medium text-primary ring-4 ring-primary/20">
                마이페이지
            </span>
        </div>
    );
}

export default MiniHeaderPreview;
