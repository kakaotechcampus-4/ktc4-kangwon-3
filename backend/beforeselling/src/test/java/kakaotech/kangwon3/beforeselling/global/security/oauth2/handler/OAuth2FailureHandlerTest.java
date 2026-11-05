package kakaotech.kangwon3.beforeselling.global.security.oauth2.handler;

import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OAuth2FailureHandlerTest {

    private static final String DEFAULT_REDIRECT_URI = "http://localhost:5173/oauth/callback";
    private static final String OTHER_ALLOWED_REDIRECT_URI = "https://palgijeone.com/oauth/callback";

    private final OAuth2FailureHandler failureHandler = new OAuth2FailureHandler(
            new OAuth2RedirectCookieProvider(new AppProperties(
                    new AppProperties.Cors(List.of()),
                    new AppProperties.OAuth2(List.of(DEFAULT_REDIRECT_URI, OTHER_ALLOWED_REDIRECT_URI)),
                    new AppProperties.Cookie(true, "Lax"))));

    private final MockHttpServletRequest request = new MockHttpServletRequest();
    private final MockHttpServletResponse response = new MockHttpServletResponse();

    @Test
    @DisplayName("서비스 예외로 로그인에 실패하면 그 에러 코드를 담아 리다이렉트한다.")
    void onAuthenticationFailure_withBaseExceptionCause_thenRedirectWithItsCode() throws Exception {
        // given
        BaseException cause = new BaseException(AuthResponseCode.UNSUPPORTED_SOCIAL_PROVIDER);
        OAuth2AuthenticationException exception = new OAuth2AuthenticationException(
                new OAuth2Error(cause.getResponseCode().getCode()), cause);

        // when
        failureHandler.onAuthenticationFailure(request, response, exception);

        // then
        assertThat(response.getRedirectedUrl())
                .isEqualTo(DEFAULT_REDIRECT_URI + "?error=" + AuthResponseCode.UNSUPPORTED_SOCIAL_PROVIDER.getCode());
    }

    @Test
    @DisplayName("그 밖의 이유로 로그인에 실패하면 소셜 로그인 실패 코드를 담아 리다이렉트한다.")
    void onAuthenticationFailure_withOtherCause_thenRedirectWithLoginFailedCode() throws Exception {
        // given
        OAuth2AuthenticationException exception = new OAuth2AuthenticationException(new OAuth2Error("invalid_request"));

        // when
        failureHandler.onAuthenticationFailure(request, response, exception);

        // then
        assertThat(response.getRedirectedUrl())
                .isEqualTo(DEFAULT_REDIRECT_URI + "?error=" + AuthResponseCode.OAUTH2_LOGIN_FAILED.getCode());
    }

    @Test
    @DisplayName("저장된 리다이렉트 주소로 이동하고 리다이렉트 쿠키를 만료시킨다.")
    void onAuthenticationFailure_withRedirectCookie_thenRedirectToItAndExpireCookie() throws Exception {
        // given
        request.setCookies(new Cookie(OAuth2RedirectCookieProvider.COOKIE_NAME, OTHER_ALLOWED_REDIRECT_URI));
        OAuth2AuthenticationException exception = new OAuth2AuthenticationException(new OAuth2Error("invalid_request"));

        // when
        failureHandler.onAuthenticationFailure(request, response, exception);

        // then
        assertThat(response.getRedirectedUrl()).startsWith(OTHER_ALLOWED_REDIRECT_URI + "?error=");
        assertThat(response.getHeader(HttpHeaders.SET_COOKIE))
                .startsWith(OAuth2RedirectCookieProvider.COOKIE_NAME + "=;")
                .contains("Max-Age=0");
    }
}
