import apiClient from "./client";

export enum SocialProvider {
    Kakao = "KAKAO",
    Naver = "NAVER",
    Google = "GOOGLE",
}

export interface UserInfo {
    name: string
    email: string
    socialProvider: SocialProvider
}

/** 내 정보 조회 */
export async function getMyInfo() {
    const response = await apiClient.get("/api/v1/users/me");
    return response.data.data as UserInfo;
}

/** 내 정보 수정(이름만 변경 가능) */
export async function updateMyInfo(payload: { name: string }) {
    const response = await apiClient.patch("/api/v1/users/me", payload);
    return response.data.data as UserInfo;
}

/** 회원 탈퇴 */
export async function withdraw() {
    const response = await apiClient.delete("/api/v1/users/me");
    return response.data.data;
}
