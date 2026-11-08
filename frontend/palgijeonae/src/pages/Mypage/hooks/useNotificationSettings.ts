import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getNotificationSettings, updateNotificationSettings } from "@/api/users.ts";
import { LAW_AMENDMENTS_QUERY_KEY } from "@/pages/Mypage/constants.ts";

const NOTIFICATION_SETTINGS_QUERY_KEY = ["notificationSettings"];

// 알림 설정 조회.
export function useNotificationSettings() {
    return useQuery({
        queryKey: NOTIFICATION_SETTINGS_QUERY_KEY,
        queryFn: getNotificationSettings,
    });
}

// 알림 설정 수정. 성공하면 응답으로 설정 캐시를 갱신하고, 개정 알림은 다시 불러온다(끄면 빈 목록, 켜면 다시 보인다).
export function useUpdateNotificationSettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: updateNotificationSettings,
        onSuccess: (data) => {
            queryClient.setQueryData(NOTIFICATION_SETTINGS_QUERY_KEY, data);
            queryClient.invalidateQueries({ queryKey: LAW_AMENDMENTS_QUERY_KEY });
        },
    });
}
