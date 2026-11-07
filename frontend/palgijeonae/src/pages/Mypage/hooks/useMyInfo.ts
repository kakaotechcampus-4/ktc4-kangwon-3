import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getMyInfo, updateMyInfo } from "@/api/users.ts";

const MY_INFO_QUERY_KEY = ["myInfo"];

// 내 정보 조회.
export function useMyInfo() {
    return useQuery({
        queryKey: MY_INFO_QUERY_KEY,
        queryFn: getMyInfo,
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
