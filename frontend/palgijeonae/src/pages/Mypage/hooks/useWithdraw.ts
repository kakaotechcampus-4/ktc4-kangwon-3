import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { withdraw } from "@/api/user.ts";
import { useAuthStore } from "@/store/useAuthStore.ts";

// 회원 탈퇴. 성공 시 아래 순서를 지킨다 — 순서가 바뀌면 ProtectedRoute의 /login 리다이렉트나 빈 토큰으로의 refetch가 발생한다.
export function useWithdraw() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const logout = useAuthStore((state) => state.logout);

    return useMutation({
        mutationFn: withdraw,
        onSuccess: () => {
            navigate("/", { replace: true });
            logout();
            queryClient.clear();
            alert("탈퇴가 완료되었습니다. 그동안 팔기전에를 이용해주셔서 감사합니다.");
        },
    });
}
