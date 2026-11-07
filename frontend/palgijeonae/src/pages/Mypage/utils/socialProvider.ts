import { SocialProvider } from "@/api/users.ts";
import googleIcon from "@/assets/login-google.png";
import kakaoIcon from "@/assets/login-kakao.png";
import naverIcon from "@/assets/login-naver.png";

interface SocialProviderInfo {
    label: string
    icon: string
}

// 소셜 로그인 제공자별 표시 라벨·아이콘
export const SOCIAL_PROVIDER_INFO: Record<SocialProvider, SocialProviderInfo> = {
    [SocialProvider.Kakao]: { label: "카카오", icon: kakaoIcon },
    [SocialProvider.Naver]: { label: "네이버", icon: naverIcon },
    [SocialProvider.Google]: { label: "구글", icon: googleIcon },
};
