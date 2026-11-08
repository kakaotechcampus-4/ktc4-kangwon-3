import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getMyInfo, updateMyInfo } from "@/api/users.ts";

const MY_INFO_QUERY_KEY = ["myInfo"];

// 자주 변하지 않고 자주 쓰는 값이므로 5분 캐시 유지.
const MY_INFO_STALE_TIME_MS = 5 * 60 * 1000;

// 내 정보 조회.
export function useMyInfo() {
    return useQuery({
        queryKey: MY_INFO_QUERY_KEY,
        queryFn: getMyInfo,
        staleTime: MY_INFO_STALE_TIME_MS,
    });
}

// 내 정보 수정. 성공하면 응답으로 캐시만 갱신하고 다시 불러오지 않는다.
export function useUpdateMyInfo() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: updateMyInfo,
        onSuccess: (data) => {
            queryClient.setQueryData(MY_INFO_QUERY_KEY, data);
        },
    });
}
