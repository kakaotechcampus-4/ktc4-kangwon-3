import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getNotificationSettings, updateNotificationSettings } from "@/api/users.ts";

const NOTIFICATION_SETTINGS_QUERY_KEY = ["notificationSettings"];

// 알림 설정 조회.
export function useNotificationSettings() {
    return useQuery({
        queryKey: NOTIFICATION_SETTINGS_QUERY_KEY,
        queryFn: getNotificationSettings,
    });
}

// 알림 설정 수정. 성공하면 응답으로 캐시만 갱신하고 다시 불러오지 않는다.
export function useUpdateNotificationSettings() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: updateNotificationSettings,
        onSuccess: (data) => {
            queryClient.setQueryData(NOTIFICATION_SETTINGS_QUERY_KEY, data);
        },
    });
}
