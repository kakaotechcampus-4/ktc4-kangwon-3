import SectionIntro from "@/components/common/SectionIntro";
import NotificationSettings from "@/pages/Mypage/components/NotificationSettings.tsx";
import ProfileSection from "@/pages/Mypage/components/ProfileSection.tsx";
import WithdrawSection from "@/pages/Mypage/components/WithdrawSection.tsx";

function MyPage() {
    return (
        <div className="flex w-full flex-col gap-8">
            <SectionIntro title="마이페이지" description="회원 정보와 알림 설정을 관리할 수 있어요" />
            <ProfileSection />
            <NotificationSettings />
            <WithdrawSection />
        </div>
    );
}

export default MyPage;
