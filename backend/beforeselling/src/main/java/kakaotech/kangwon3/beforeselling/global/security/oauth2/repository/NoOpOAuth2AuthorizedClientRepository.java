package kakaotech.kangwon3.beforeselling.global.security.oauth2.repository;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;

/**
 * 제공자의 액세스/리프레시 토큰을 서버에 보관하지 않습니다.
 * 기본 구현(InMemory)은 로그인한 모든 사용자의 제공자 토큰을 메모리에 무기한 보관하므로 명시적으로 비활성화합니다.
 */
public class NoOpOAuth2AuthorizedClientRepository implements OAuth2AuthorizedClientRepository {

    @Override
    public <T extends OAuth2AuthorizedClient> T loadAuthorizedClient(String clientRegistrationId,
                                                                     Authentication principal,
                                                                     HttpServletRequest request) {
        return null;
    }

    @Override
    public void saveAuthorizedClient(OAuth2AuthorizedClient authorizedClient, Authentication principal,
                                     HttpServletRequest request, HttpServletResponse response) {
        // no-op
    }

    @Override
    public void removeAuthorizedClient(String clientRegistrationId, Authentication principal,
                                       HttpServletRequest request, HttpServletResponse response) {
        // no-op
    }
}
