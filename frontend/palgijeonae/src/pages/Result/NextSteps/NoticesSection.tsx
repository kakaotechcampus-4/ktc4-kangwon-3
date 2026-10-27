import DefaultBox from "@/components/common/DefaultBox";

interface NoticesSectionProps {
    notices: string[]
}

function NoticesSection({ notices }: NoticesSectionProps) {
    if (notices.length === 0) {
        return null;
    }

    return (
        <DefaultBox tone="warning" className="gap-3">
            <h3 className="text-lg leading-tight font-bold text-status-warning">유의사항</h3>
            {notices.map((notice, index) => (
                <p key={index} className="text-sm leading-relaxed text-status-warning">
                    • {notice}
                </p>
            ))}
        </DefaultBox>
    );
}

export default NoticesSection;
