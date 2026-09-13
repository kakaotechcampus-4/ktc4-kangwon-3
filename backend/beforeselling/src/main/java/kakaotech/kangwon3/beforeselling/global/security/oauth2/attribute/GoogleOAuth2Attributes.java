package kakaotech.kangwon3.beforeselling.global.security.oauth2.attribute;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;

import java.util.Map;

/**
 * 구글 사용자 정보 응답 구조:
 * { "sub": "...", "email": "...", "name": "...", "picture": "..." }
 */
public final class GoogleOAuth2Attributes implements OAuth2Attributes {

    private final Map<String, Object> attributes;

    public GoogleOAuth2Attributes(Map<String, Object> attributes) {
        this.attributes = attributes;
    }

    @Override
    public SocialProvider getProvider() {
        return SocialProvider.GOOGLE;
    }

    @Override
    public String getSocialId() {
        return OAuth2Attributes.stringValue(attributes, "sub");
    }

    @Override
    public String getEmail() {
        return OAuth2Attributes.stringValue(attributes, "email");
    }

    @Override
    public String getName() {
        return OAuth2Attributes.stringValue(attributes, "name");
    }

    @Override
    public Map<String, Object> getAttributes() {
        return attributes;
    }
}
