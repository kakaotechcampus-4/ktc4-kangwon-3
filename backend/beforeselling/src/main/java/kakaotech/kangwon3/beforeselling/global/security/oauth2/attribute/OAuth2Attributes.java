package kakaotech.kangwon3.beforeselling.global.security.oauth2.attribute;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;

import java.util.Map;

/**
 * 소셜 제공자별 사용자 정보 응답을 공통 형태(provider, socialId, email, name)로 변환합니다.
 */
public sealed interface OAuth2Attributes
        permits KakaoOAuth2Attributes, NaverOAuth2Attributes, GoogleOAuth2Attributes {

    SocialProvider getProvider();

    String getSocialId();

    /** 제공자/동의 항목에 따라 없을 수 있으므로 null 허용 */
    String getEmail();

    String getName();

    Map<String, Object> getAttributes();

    static OAuth2Attributes of(String registrationId, Map<String, Object> attributes) {
        SocialProvider provider = SocialProvider.fromRegistrationId(registrationId)
                .orElseThrow(() -> new BaseException(AuthResponseCode.UNSUPPORTED_SOCIAL_PROVIDER));

        return switch (provider) {
            case KAKAO -> new KakaoOAuth2Attributes(attributes);
            case NAVER -> new NaverOAuth2Attributes(attributes);
            case GOOGLE -> new GoogleOAuth2Attributes(attributes);
        };
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> nestedMap(Map<String, Object> attributes, String key) {
        Object value = attributes == null ? null : attributes.get(key);
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    static String stringValue(Map<String, Object> attributes, String key) {
        Object value = attributes == null ? null : attributes.get(key);
        return value == null ? null : String.valueOf(value);
    }
}
