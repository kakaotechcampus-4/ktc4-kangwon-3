package kakaotech.kangwon3.beforeselling.global.security.oauth2.attribute;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;

import java.util.Map;

/**
 * 네이버 사용자 정보 응답 구조:
 * { "resultcode": "00", "message": "success", "response": { "id": "...", "email": "...", "name": "..." } }
 */
public final class NaverOAuth2Attributes implements OAuth2Attributes {

    private final Map<String, Object> attributes;
    private final Map<String, Object> response;

    public NaverOAuth2Attributes(Map<String, Object> attributes) {
        this.attributes = attributes;
        this.response = OAuth2Attributes.nestedMap(attributes, "response");
    }

    @Override
    public SocialProvider getProvider() {
        return SocialProvider.NAVER;
    }

    @Override
    public String getSocialId() {
        return OAuth2Attributes.stringValue(response, "id");
    }

    @Override
    public String getEmail() {
        return OAuth2Attributes.stringValue(response, "email");
    }

    @Override
    public String getName() {
        return OAuth2Attributes.stringValue(response, "name");
    }

    @Override
    public Map<String, Object> getAttributes() {
        return attributes;
    }
}
