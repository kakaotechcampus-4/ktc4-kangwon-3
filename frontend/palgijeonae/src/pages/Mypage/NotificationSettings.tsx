import { useState } from "react";

import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";

import SettingToggleRow from "./SettingToggleRow.tsx";

// 추후 다른 세팅 확장성을 위해 SettingToggleRow를 여러 개를 포함하는 컴포넌트로 분리
function NotificationSettings() {
    // TODO: 백엔드 연동 전까지 쓰는 로컬 상태. 실제로는 설정 조회/변경 API와 연결해야 한다.
    const [revisionAlertEnabled, setRevisionAlertEnabled] = useState(false);

    return (
        <DefaultBox className="flex flex-col gap-5">
            <SectionIntro title="알림 설정" size="xl"/>
            <hr className="w-full border-neutral-border" />
            <SettingToggleRow
                title="고시 개정 알림"
                description="관련 법령·고시가 바뀌면 마이페이지 상단에 알려드립니다."
                checked={revisionAlertEnabled}
                onChange={setRevisionAlertEnabled}
            />
        </DefaultBox>
    );
}

export default NotificationSettings;
