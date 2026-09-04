package kakaotech.kangwon3.beforeselling.global.security.oauth2.attribute;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;

import java.util.Map;

/**
 * 카카오 사용자 정보 응답 구조:
 * { "id": 123, "kakao_account": { "email": "...", "profile": { "nickname": "..." } } }
 */
public final class KakaoOAuth2Attributes implements OAuth2Attributes {

    private final Map<String, Object> attributes;
    private final Map<String, Object> kakaoAccount;
    private final Map<String, Object> profile;

    public KakaoOAuth2Attributes(Map<String, Object> attributes) {
        this.attributes = attributes;
        this.kakaoAccount = OAuth2Attributes.nestedMap(attributes, "kakao_account");
        this.profile = OAuth2Attributes.nestedMap(kakaoAccount, "profile");
    }

    @Override
    public SocialProvider getProvider() {
        return SocialProvider.KAKAO;
    }

    @Override
    public String getSocialId() {
        return OAuth2Attributes.stringValue(attributes, "id");
    }

    @Override
    public String getEmail() {
        return OAuth2Attributes.stringValue(kakaoAccount, "email");
    }

    @Override
    public String getName() {
        return OAuth2Attributes.stringValue(profile, "nickname");
    }

    @Override
    public Map<String, Object> getAttributes() {
        return attributes;
    }
}
