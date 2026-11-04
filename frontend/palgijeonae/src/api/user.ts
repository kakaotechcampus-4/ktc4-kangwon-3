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

// TODO: 내 정보 조회·수정 API가 develop에 병합되면 apiClient 호출로 되돌리고, 아래 목업은 api/mock/userMock.ts로 옮긴다.
let mockUserInfo: UserInfo = {
    name: "홍길동",
    email: "hong@example.com",
    socialProvider: SocialProvider.Kakao,
};

/** 내 정보 조회 */
export async function getMyInfo(): Promise<UserInfo> {
    return mockUserInfo;
}

/** 내 정보 수정(이름만 변경 가능) */
export async function updateMyInfo(payload: { name: string }): Promise<UserInfo> {
    mockUserInfo = { ...mockUserInfo, name: payload.name };
    return mockUserInfo;
}

/** 회원 탈퇴. develop에 이미 있는 API라 목업 처리하지 않는다. */
export async function withdraw(): Promise<void> {
    await apiClient.delete("/api/v1/users/me");
}
