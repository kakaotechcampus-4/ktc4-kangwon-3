import { type NotificationSettings, SocialProvider, type UserInfo } from "@/api/users";

/**
 * 로컬에서 BE 없이 테스트할 때만 쓰는 픽스처.
 * 쓰려면 호출부의 import를 "@/api/users" 대신 "@/api/mock/users"로 바꾸면 된다.
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

let mockNotificationSettings: NotificationSettings = { lawAmendmentAlertEnabled: true };

/** 목업 개정 목록이 알림 설정을 따르도록 mock/lawAmendments.ts가 읽는다. */
export function isLawAmendmentAlertEnabled(): boolean {
    return mockNotificationSettings.lawAmendmentAlertEnabled;
}

/** 개발용 알림 설정 조회 함수 */
export async function getNotificationSettings(): Promise<NotificationSettings> {
    return mockNotificationSettings;
}

/** 개발용 알림 설정 수정 함수. 전달한 값으로 목업 상태를 바꿔서 응답한다. */
export async function updateNotificationSettings(payload: NotificationSettings): Promise<NotificationSettings> {
    mockNotificationSettings = { ...payload };
    return mockNotificationSettings;
}
