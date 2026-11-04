import type { UserInfo } from "@/api/user";
import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";

interface UserInfoProps {
    userInfo: UserInfo
}

function UserInfo({ userInfo }: UserInfoProps) {
    return (
        <DefaultBox className="flex flex-col gap-5">
            <SectionIntro title="회원 정보" size="xl"/>
            <hr className="w-full border-neutral-border" />
        </DefaultBox>
    );
}

export default UserInfo;