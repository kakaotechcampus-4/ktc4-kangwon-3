import { SocialProvider, type UserInfo } from "@/api/user";

/**
 * 로컬에서 BE 없이 테스트할 때만 쓰는 픽스처.
 * 쓰려면 호출부의 import를 "@/api/user" 대신 "@/api/mock/userMock"으로 바꾸면 된다.
 */

let mockUserInfo: UserInfo = {
    name: "홍길동",
    email: "hong@example.com",
    socialProvider: SocialProvider.Kakao,
};

/** 개발용 내 정보 조회 함수 */
export async function getMyInfo(): Promise<UserInfo> {
    return mockUserInfo;
}

/** 개발용 내 정보 수정 함수. 전달한 name으로 목업 상태를 바꿔서 응답한다. */
export async function updateMyInfo(payload: { name: string }): Promise<UserInfo> {
    mockUserInfo = { ...mockUserInfo, name: payload.name };
    return mockUserInfo;
}
