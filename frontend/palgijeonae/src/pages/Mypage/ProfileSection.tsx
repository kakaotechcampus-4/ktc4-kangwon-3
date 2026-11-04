import { useState } from "react";

import { getErrorMessage } from "@/api/client.ts";
import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import LoadingSpinner from "@/components/common/LoadingSpinner/index.tsx";
import SectionIntro from "@/components/common/SectionIntro/index.tsx";

import { NAME_MAX_LENGTH } from "./constraints.ts";
import EditableInfoRow from "./EditableInfoRow.tsx";
import { SOCIAL_PROVIDER_INFO } from "./socialProvider.ts";
import { useMyInfo, useUpdateMyInfo } from "./useMyInfo.ts";

/** 마이페이지 "회원 정보" 섹션. 이름·이메일·로그인 방식을 보여주고, 이름만 인라인으로 수정할 수 있다. */
function ProfileSection() {
    const { data: userInfo, isPending, isError, refetch } = useMyInfo();
    const { mutate: saveName, isPending: isSaving } = useUpdateMyInfo();
    const [draftName, setDraftName] = useState("");

    const handleSave = () => {
        saveName({ name: draftName.trim() }, {
            onError: (error) => {
                alert(getErrorMessage(error, "이름 수정에 실패했습니다. 다시 시도해주세요."));
            },
        });
    };

    return (
        <DefaultBox className="flex flex-col gap-5">
            <SectionIntro title="회원 정보" size="xl" />
            <hr className="w-full border-neutral-border" />
            {isPending ? (
                <LoadingSpinner />
            ) : isError || !userInfo ? (
                <div className="flex w-full flex-col items-center gap-3 py-12">
                    <p className="text-sm font-medium text-status-danger">회원 정보를 불러오지 못했어요.</p>
                    <button
                        type="button"
                        onClick={() => refetch()}
                        className="cursor-pointer text-sm font-medium text-neutral-border underline underline-offset-2"
                    >
                        다시 시도
                    </button>
                </div>
            ) : (
                <>
                    <div className="flex w-full flex-col gap-4">
                        <EditableInfoRow
                            title="이름"
                            description={userInfo.name}
                            editable
                            maxLength={NAME_MAX_LENGTH}
                            onChange={setDraftName}
                            disabled={isSaving}
                            onSave={handleSave}
                        />
                        <div className="flex items-center gap-4">
                            <span className="w-16 shrink-0 text-sm font-semibold text-neutral-label">이메일</span>
                            <span className="text-base text-black">{userInfo.email}</span>
                        </div>
                        <div className="flex items-center gap-4">
                            <span className="w-16 shrink-0 text-sm font-semibold text-neutral-label">로그인</span>
                            <span className="flex items-center gap-2 text-base text-black">
                                <img src={SOCIAL_PROVIDER_INFO[userInfo.socialProvider].icon} alt="" className="h-5 w-5" />
                                {SOCIAL_PROVIDER_INFO[userInfo.socialProvider].label} 계정으로 가입
                            </span>
                        </div>
                    </div>
                    <p className="text-sm text-neutral-border">이메일은 소셜 계정 정보를 따르기 때문에 여기서 바꿀 수 없어요.</p>
                </>
            )}
        </DefaultBox>
    );
}

export default ProfileSection;
