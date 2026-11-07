import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/client";
import { retryDiagnosis } from "@/api/result";

/** 실패한 상품을 재진단하고, 성공하면 진행 화면으로 이동한다. */
export function useRetryDiagnosis(productId: string, diagnosesId: string) {
    const navigate = useNavigate();

    return useMutation({
        mutationFn: () => retryDiagnosis(productId),
        onSuccess: () => {
            navigate(`/judgement/${diagnosesId}`);
        },
        onError: (error) => {
            alert(getErrorMessage(error, "재진단 요청에 실패했습니다. 다시 시도해주세요."));
        },
    });
}
