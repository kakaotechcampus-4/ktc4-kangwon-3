import { useQuery } from "@tanstack/react-query";

import { getLawAmendments } from "@/api/lawAmendments.ts";
import { LAW_AMENDMENTS_QUERY_KEY } from "@/pages/Products/constants.ts";

// 법령 개정 알림 조회.
export function useLawAmendments() {
    return useQuery({
        queryKey: LAW_AMENDMENTS_QUERY_KEY,
        queryFn: getLawAmendments,
    });
}
