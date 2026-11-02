import { useQuery } from "@tanstack/react-query";

import { getDiagnosesPolling } from "@/api/judgement";

/** 진단서 안의 상품들을 조회한다. 응답의 pollIntervalMs가 있으면 그 간격으로, null이면 더 이상 폴링하지 않는다. */
export function useJudgementProducts(diagnosesId: string | undefined, enabled: boolean) {
    return useQuery({
        queryKey: ["judgement", diagnosesId],
        queryFn: () => getDiagnosesPolling(diagnosesId!),
        enabled,
        refetchInterval: (query) => query.state.data?.pollIntervalMs ?? false,
    });
}
