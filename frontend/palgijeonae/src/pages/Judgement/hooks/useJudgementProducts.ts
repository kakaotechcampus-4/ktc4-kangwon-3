import { useQuery } from "@tanstack/react-query";

import { isInvalidIdError } from "@/api/core/invalidId";
import { getDiagnosesPolling } from "@/api/diagnoses";

/** 진단서 안의 상품들을 조회한다. 응답의 pollIntervalMs가 있으면 그 간격으로, null이면 더 이상 폴링하지 않는다. */
export function useJudgementProducts(diagnosesId: string | undefined, enabled: boolean) {
    const query = useQuery({
        queryKey: ["judgement", diagnosesId],
        queryFn: () => getDiagnosesPolling(diagnosesId!),
        enabled,
        refetchInterval: (query) => query.state.data?.pollIntervalMs ?? false,
    });

    // 형식이 잘못됐거나 존재하지 않는 id로 접근한 경우(400, 404)
    const isInvalidId = isInvalidIdError(query.error);

    return { ...query, isInvalidId };
}
