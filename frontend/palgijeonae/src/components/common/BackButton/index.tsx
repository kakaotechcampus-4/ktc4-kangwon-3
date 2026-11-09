import { useLocation, useNavigate } from "react-router-dom";

import nextPageIcon from "@/assets/mypage-next-page.svg";
import { hasFromState } from "@/lib/fromState";

interface BackButtonProps {
    // 이전 경로를 모를 때 돌아갈 진행 화면(/judgement/:diagnosesId)을 정하는 값
    diagnosesId?: string
}

/** 이전 화면으로 돌아가는 버튼. 앱 안에서 온 경우(state.from) 히스토리를 한 칸 되돌리고, 아니면 진행 화면으로 이동한다. */
function BackButton({ diagnosesId }: BackButtonProps) {
    const navigate = useNavigate();
    const { state } = useLocation();
    const cameFromApp = hasFromState(state);

    // 돌아갈 곳을 알 수 없으면(이전 경로도 diagnosesId도 없음) 버튼 자체를 숨긴다.
    if (!cameFromApp && !diagnosesId) {
        return null;
    }

    const handleClick = () => {
        if (cameFromApp) {
            navigate(-1);
            return;
        }
        navigate(`/judgement/${diagnosesId}`, { replace: true });
    };

    return (
        <button type="button" onClick={handleClick} className="flex cursor-pointer items-center gap-1 py-1 text-sm font-medium text-neutral-muted">
            <img src={nextPageIcon} alt="" className="h-4 w-4 -scale-x-100" />
            이전으로
        </button>
    );
}

export default BackButton;
