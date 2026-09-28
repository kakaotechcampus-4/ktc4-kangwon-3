import bell from "@/assets/mypage-bell.svg"
import calendar from "@/assets/mypage-calendar.svg"
import DefaultBox from "@/components/common/DefaultBox";

interface RevisionNoticeBannerProps {
    revisedDate: string
    title: string
    description: string
    onCheckClick: () => void
}

// TODO: 백엔드 api 스키마가 마련되지 않아 연동과 관련한 로직은 별도의 브랜치에서 진행한다.
function RevisionNoticeBanner({ revisedDate, title, description, onCheckClick }: RevisionNoticeBannerProps) {
    return (
        <DefaultBox tone="warning">
            <div className="flex flex-row gap-5 items-center">
                <img src={bell} alt="알림 아이콘" className="w-8 h-8"/>
                <div className="bg-white px-3 py-1 rounded-full border border-status-warning text-status-warning text-sm font-medium">개정 알림</div>
                <div className="flex flex-row gap-2 items-center">
                    <img src={calendar} alt="캘린더 아이콘" className="w-7 h-7"/>
                    <p className="text-base font-bold text-status-warning">개정 일자</p>
                    <p className="text-sm font-semibold text-status-warning">{revisedDate}</p>
                </div>
            </div>
            <div className="flex flex-col gap-2">
                <p className="text-base font-medium">{title}</p>
                <p className="whitespace-pre-line text-base font-medium text-neutral-text">{description}</p>
            </div>
            <div className="flex w-full justify-end">
                <button type="button" onClick={onCheckClick} className="px-5 py-2 cursor-pointer text-sm font-semibold rounded-full bg-status-warning text-white">재확인 필요 상품 확인하기</button>
            </div>
        </DefaultBox>
    );
}

export default RevisionNoticeBanner;
