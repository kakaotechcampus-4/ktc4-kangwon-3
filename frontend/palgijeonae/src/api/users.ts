import apiClient from "@/api/core/client";

export enum SocialProvider {
    Kakao = "KAKAO",
    Naver = "NAVER",
    Google = "GOOGLE",
}

export interface UserInfo {
    name: string
    // 소셜 계정에서 이메일을 받지 못한 회원은 null이다.
    email: string | null
    socialProvider: SocialProvider
}

/** 내 정보 조회 */
export async function getMyInfo(): Promise<UserInfo> {
    const response = await apiClient.get("/api/v1/users/me");
    return response.data.data as UserInfo;
}

/** 내 정보 수정(이름만 변경 가능) */
export async function updateMyInfo(payload: { name: string }): Promise<UserInfo> {
    const response = await apiClient.patch("/api/v1/users/me", payload);
    return response.data.data as UserInfo;
}

/** 회원 탈퇴 */
export async function withdraw(): Promise<void> {
    await apiClient.delete("/api/v1/users/me");
}

export interface NotificationSettings {
    lawAmendmentAlertEnabled: boolean
}

/** 알림 설정 조회 */
export async function getNotificationSettings(): Promise<NotificationSettings> {
    const response = await apiClient.get("/api/v1/users/me/notification-settings");
    return response.data.data as NotificationSettings;
}

/** 알림 설정 수정 */
export async function updateNotificationSettings(payload: NotificationSettings): Promise<NotificationSettings> {
    const response = await apiClient.patch("/api/v1/users/me/notification-settings", payload);
    return response.data.data as NotificationSettings;
}
