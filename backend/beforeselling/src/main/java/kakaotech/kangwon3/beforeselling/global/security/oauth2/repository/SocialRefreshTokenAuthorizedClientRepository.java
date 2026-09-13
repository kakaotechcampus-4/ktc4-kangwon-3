package kakaotech.kangwon3.beforeselling.global.security.oauth2.repository;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.security.oauth2.core.OAuth2RefreshToken;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class SocialRefreshTokenAuthorizedClientRepository implements OAuth2AuthorizedClientRepository {

    private final UserService userService;

    @Override
    public <T extends OAuth2AuthorizedClient> T loadAuthorizedClient(String clientRegistrationId,
                                                                     Authentication principal,
                                                                     HttpServletRequest request) {
        return null;
    }

    @Override
    public void saveAuthorizedClient(OAuth2AuthorizedClient authorizedClient, Authentication principal,
                                     HttpServletRequest request, HttpServletResponse response) {
        OAuth2RefreshToken refreshToken = authorizedClient.getRefreshToken();
        if (refreshToken == null) {
            return;
        }
        if (!(principal.getPrincipal() instanceof CustomOAuth2User customOAuth2User)) {
            log.warn("알 수 없는 principal 타입이라 소셜 refresh_token 캡처를 건너뜁니다. type={}",
                    principal.getPrincipal().getClass());
            return;
        }
        SocialProvider provider = SocialProvider
                .fromRegistrationId(authorizedClient.getClientRegistration().getRegistrationId())
                .orElse(null);
        if (provider == null) {
            return;
        }

        try {
            userService.updateSocialRefreshToken(customOAuth2User.userId(), refreshToken.getTokenValue());
        } catch (Exception e) {
            log.error("소셜 refresh_token 저장 실패. userId={}, provider={}", customOAuth2User.userId(), provider, e);
        }
    }

    @Override
    public void removeAuthorizedClient(String clientRegistrationId, Authentication principal,
                                       HttpServletRequest request, HttpServletResponse response) {
        // no-op
    }
}
