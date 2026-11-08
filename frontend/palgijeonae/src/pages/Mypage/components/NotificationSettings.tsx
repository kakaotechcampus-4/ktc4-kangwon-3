import { getErrorMessage } from "@/api/core/client.ts";
import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";
import { useNotificationSettings, useUpdateNotificationSettings } from "@/pages/Mypage/hooks/useNotificationSettings.ts";

import SettingToggleRow from "./SettingToggleRow.tsx";

// 추후 다른 세팅 확장성을 위해 SettingToggleRow를 여러 개를 포함하는 컴포넌트로 분리
function NotificationSettings() {
    const { data, isPending } = useNotificationSettings();
    const { mutate, isPending: isUpdating } = useUpdateNotificationSettings();

    const handleLawAmendmentAlertChange = (enabled: boolean) => {
        mutate(
            { lawAmendmentAlertEnabled: enabled },
            {
                onError: (error) => {
                    alert(getErrorMessage(error, "알림 설정을 바꾸지 못했어요. 다시 시도해주세요."));
                },
            },
        );
    };

    return (
        <DefaultBox className="flex flex-col gap-5">
            <SectionIntro title="알림 설정" size="xl"/>
            <hr className="w-full border-neutral-line" />
            <SettingToggleRow
                title="법령 개정 알림"
                description="진단 근거 법령이 바뀌면 마이페이지 상단에 알려드려요."
                checked={data?.lawAmendmentAlertEnabled ?? false}
                onChange={handleLawAmendmentAlertChange}
                disabled={isPending || isUpdating}
            />
        </DefaultBox>
    );
}

export default NotificationSettings;
