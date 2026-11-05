package kakaotech.kangwon3.beforeselling.global.security.oauth2.handler;

import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.TestingAuthenticationToken;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class OAuth2SuccessHandlerTest {

    private static final String DEFAULT_REDIRECT_URI = "http://localhost:5173/oauth/callback";
    private static final String OTHER_ALLOWED_REDIRECT_URI = "https://palgijeone.com/oauth/callback";
    private static final UUID USER_ID = UUID.randomUUID();
    private static final TokenPair TOKEN_PAIR = new TokenPair("access-token", "refresh-token", "jti", 1800);

    @Mock
    private AuthTokenService authTokenService;

    private OAuth2SuccessHandler successHandler;

    private final MockHttpServletRequest request = new MockHttpServletRequest();
    private final MockHttpServletResponse response = new MockHttpServletResponse();

    @BeforeEach
    void setUp() {
        AppProperties appProperties = new AppProperties(
                new AppProperties.Cors(List.of()),
                new AppProperties.OAuth2(List.of(DEFAULT_REDIRECT_URI, OTHER_ALLOWED_REDIRECT_URI)),
                new AppProperties.Cookie(true, "Lax"));
        JwtProperties jwtProperties = new JwtProperties("secret", Duration.ofMinutes(30), Duration.ofDays(14));
        successHandler = new OAuth2SuccessHandler(authTokenService,
                new RefreshTokenCookieProvider(appProperties, jwtProperties),
                new OAuth2RedirectCookieProvider(appProperties));
    }

    @Test
    @DisplayName("로그인에 성공하면 리프레시 토큰을 쿠키로 심고, 저장된 주소로 신규 가입 여부와 함께 리다이렉트한다.")
    void onAuthenticationSuccess_thenSetRefreshTokenCookieAndRedirect() throws Exception {
        // given
        given(authTokenService.issueTokens(USER_ID, Role.USER)).willReturn(TOKEN_PAIR);
        request.setCookies(new Cookie(OAuth2RedirectCookieProvider.COOKIE_NAME, OTHER_ALLOWED_REDIRECT_URI));

        // when
        successHandler.onAuthenticationSuccess(request, response, authenticationOf(true));

        // then
        assertThat(response.getRedirectedUrl()).isEqualTo(OTHER_ALLOWED_REDIRECT_URI + "?isNewUser=true");
        assertThat(response.getHeaders(HttpHeaders.SET_COOKIE))
                .anySatisfy(cookie -> assertThat(cookie)
                        .startsWith(RefreshTokenCookieProvider.COOKIE_NAME + "=refresh-token")
                        .contains("HttpOnly"));
    }

    @Test
    @DisplayName("로그인에 성공하면 리다이렉트 쿠키를 만료시키고, 액세스 토큰은 URL에 노출하지 않는다.")
    void onAuthenticationSuccess_thenExpireRedirectCookieAndHideAccessToken() throws Exception {
        // given
        given(authTokenService.issueTokens(USER_ID, Role.USER)).willReturn(TOKEN_PAIR);
        request.setCookies(new Cookie(OAuth2RedirectCookieProvider.COOKIE_NAME, OTHER_ALLOWED_REDIRECT_URI));

        // when
        successHandler.onAuthenticationSuccess(request, response, authenticationOf(false));

        // then
        assertThat(response.getHeaders(HttpHeaders.SET_COOKIE))
                .anySatisfy(cookie -> assertThat(cookie)
                        .startsWith(OAuth2RedirectCookieProvider.COOKIE_NAME + "=;")
                        .contains("Max-Age=0"));
        assertThat(response.getRedirectedUrl()).doesNotContain("access-token");
    }

    @Test
    @DisplayName("리다이렉트 쿠키가 없으면 기본 주소로 리다이렉트한다.")
    void onAuthenticationSuccess_withoutRedirectCookie_thenRedirectToDefault() throws Exception {
        // given
        given(authTokenService.issueTokens(USER_ID, Role.USER)).willReturn(TOKEN_PAIR);

        // when
        successHandler.onAuthenticationSuccess(request, response, authenticationOf(false));

        // then
        assertThat(response.getRedirectedUrl()).isEqualTo(DEFAULT_REDIRECT_URI + "?isNewUser=false");
    }

    private TestingAuthenticationToken authenticationOf(boolean isNewUser) {
        return new TestingAuthenticationToken(new CustomOAuth2User(USER_ID, Role.USER, isNewUser, Map.of()), null);
    }
}
