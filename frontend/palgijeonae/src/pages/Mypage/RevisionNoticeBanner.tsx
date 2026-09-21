import DefaultBox from "@/components/common/DefaultBox";

interface RevisionNoticeBannerProps {
    revisedDate: string
    title: string
    description: string
    onCheckClick: () => void
}

function RevisionNoticeBanner(_props: RevisionNoticeBannerProps) {
    return (
        <DefaultBox>
            개정 알림 배너
        </DefaultBox>
    );
}

export default RevisionNoticeBanner;
