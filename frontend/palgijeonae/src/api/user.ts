import apiClient from "./client";

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
