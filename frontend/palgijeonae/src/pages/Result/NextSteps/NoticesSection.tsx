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
            <h2 className="text-xl leading-tight font-bold text-status-warning">유의사항</h2>
            {notices.map((notice, index) => (
                <p key={index} className="text-base font-medium leading-relaxed text-status-warning">
                    • {notice}
                </p>
            ))}
        </DefaultBox>
    );
}

export default NoticesSection;
