package kakaotech.kangwon3.beforeselling.global.security.oauth2.repository;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.client.OAuth2AuthorizedClient;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.security.oauth2.core.OAuth2RefreshToken;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class SocialRefreshTokenAuthorizedClientRepositoryTest {

    @Mock
    private UserService userService;

    @InjectMocks
    private SocialRefreshTokenAuthorizedClientRepository repository;

    @Test
    @DisplayName("refresh_token이 없으면 저장을 건너뛴다.")
    void saveAuthorizedClient_withoutRefreshToken_thenSkip() {
        // given
        OAuth2AuthorizedClient authorizedClient = authorizedClient("naver", null);
        Authentication principal = authenticationOf(customOAuth2User());

        // when
        repository.saveAuthorizedClient(authorizedClient, principal, null, null);

        // then
        then(userService).should(org.mockito.Mockito.never())
                .updateSocialRefreshToken(any(), any());
    }

    @Test
    @DisplayName("CustomOAuth2User가 아닌 principal이면 저장을 건너뛴다.")
    void saveAuthorizedClient_withUnknownPrincipalType_thenSkip() {
        // given
        OAuth2AuthorizedClient authorizedClient = authorizedClient("naver", "refresh-token");
        Authentication principal = UsernamePasswordAuthenticationToken.authenticated("user", null, null);

        // when
        repository.saveAuthorizedClient(authorizedClient, principal, null, null);

        // then
        then(userService).should(org.mockito.Mockito.never())
                .updateSocialRefreshToken(any(), any());
    }

    @Test
    @DisplayName("refresh_token과 CustomOAuth2User가 있으면 User의 refresh_token을 갱신한다.")
    void saveAuthorizedClient_withRefreshToken_thenUpdateUser() {
        // given
        OAuth2AuthorizedClient authorizedClient = authorizedClient("naver", "refresh-token");
        Authentication principal = authenticationOf(customOAuth2User());

        // when
        repository.saveAuthorizedClient(authorizedClient, principal, null, null);

        // then
        then(userService).should().updateSocialRefreshToken(1L, "refresh-token");
    }

    @Test
    @DisplayName("refresh_token 저장 중 예외가 발생해도 전파하지 않는다(로그인 자체를 막지 않기 위함).")
    void saveAuthorizedClient_withServiceFailure_thenDoesNotPropagate() {
        // given
        OAuth2AuthorizedClient authorizedClient = authorizedClient("naver", "refresh-token");
        Authentication principal = authenticationOf(customOAuth2User());
        willThrow(new RuntimeException("DB 오류"))
                .given(userService).updateSocialRefreshToken(any(), any());

        // when & then
        assertThatCode(() -> repository.saveAuthorizedClient(authorizedClient, principal, null, null))
                .doesNotThrowAnyException();
    }

    private CustomOAuth2User customOAuth2User() {
        return new CustomOAuth2User(1L, Role.USER, false, Map.of());
    }

    private Authentication authenticationOf(CustomOAuth2User principal) {
        return UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.getAuthorities());
    }

    private OAuth2AuthorizedClient authorizedClient(String registrationId, String refreshTokenValue) {
        ClientRegistration registration = ClientRegistration.withRegistrationId(registrationId)
                .clientId("client-id")
                .clientSecret("client-secret")
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .redirectUri("{baseUrl}/login/oauth2/code/{registrationId}")
                .authorizationUri("https://example.com/authorize")
                .tokenUri("https://example.com/token")
                .build();

        OAuth2AccessToken accessToken = new OAuth2AccessToken(
                OAuth2AccessToken.TokenType.BEARER, "access-token", Instant.now(), Instant.now().plusSeconds(3600));
        OAuth2RefreshToken refreshToken = refreshTokenValue == null
                ? null
                : new OAuth2RefreshToken(refreshTokenValue, Instant.now());

        return new OAuth2AuthorizedClient(registration, "principal-name", accessToken, refreshToken);
    }
}
