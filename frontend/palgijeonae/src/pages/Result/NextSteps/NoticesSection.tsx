interface NoticesSectionProps {
    notices: string[]
}

// TODO: 경고 톤 박스로 렌더링하고, 빈 배열이면 섹션 자체를 숨김
function NoticesSection({ notices }: NoticesSectionProps) {
    return (
        <div>
            유의사항 섹션입니다. ({notices.length}건)
        </div>
    );
}

export default NoticesSection;
