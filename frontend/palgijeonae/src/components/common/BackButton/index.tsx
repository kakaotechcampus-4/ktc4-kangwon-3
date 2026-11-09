import { useLocation, useNavigate } from "react-router-dom";

import { buttonVariants } from "@/components/common/Button/variants";
import { cn } from "@/lib/cn";
import { hasFromState } from "@/lib/fromState";

interface BackButtonProps {
    // 이전 경로를 모를 때 돌아갈 진행 화면(/judgement/:diagnosesId)을 정하는 값
    diagnosesId?: string
    className?: string
}

/** 이전 화면으로 돌아가는 버튼. 앱 안에서 온 경우(state.from) 히스토리를 한 칸 되돌리고, 아니면 진행 화면으로 이동한다. */
function BackButton({ diagnosesId, className }: BackButtonProps) {
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
        <button
            type="button"
            onClick={handleClick}
            className={cn(buttonVariants({ variant: "secondary", size: "sm" }), "gap-1 pl-2.5 pr-3.5 text-sm", className)}
        >
            <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path d="M15 6l-6 6 6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            이전으로
        </button>
    );
}

export default BackButton;
