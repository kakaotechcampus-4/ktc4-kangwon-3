package kakaotech.kangwon3.beforeselling.global.security.oauth2.repository;

import org.springframework.security.oauth2.core.endpoint.OAuth2AuthorizationRequest;

import java.util.Map;
import java.util.Set;

/**
 * {@link OAuth2AuthorizationRequest}를 JSON으로 저장하기 위한 스냅샷.
 * Spring Security 내부 타입의 직렬화 규칙(Jackson 모듈)에 의존하지 않도록 필요한 필드만 직접 보관합니다.
 * attributes에는 registration_id, (OIDC 사용 시) nonce 등이 담기므로 그대로 보존합니다.
 */
public record OAuth2AuthorizationRequestSnapshot(
        String authorizationUri,
        String clientId,
        String redirectUri,
        Set<String> scopes,
        String state,
        Map<String, Object> additionalParameters,
        Map<String, Object> attributes,
        String authorizationRequestUri
) {

    public static OAuth2AuthorizationRequestSnapshot from(OAuth2AuthorizationRequest request) {
        return new OAuth2AuthorizationRequestSnapshot(
                request.getAuthorizationUri(),
                request.getClientId(),
                request.getRedirectUri(),
                request.getScopes(),
                request.getState(),
                request.getAdditionalParameters(),
                request.getAttributes(),
                request.getAuthorizationRequestUri()
        );
    }

    public OAuth2AuthorizationRequest toAuthorizationRequest() {
        // authorization_code 그랜트만 사용하므로 고정
        return OAuth2AuthorizationRequest.authorizationCode()
                .authorizationUri(authorizationUri)
                .clientId(clientId)
                .redirectUri(redirectUri)
                .scopes(scopes)
                .state(state)
                .additionalParameters(additionalParameters)
                .attributes(attributes)
                .authorizationRequestUri(authorizationRequestUri)
                .build();
    }
}
