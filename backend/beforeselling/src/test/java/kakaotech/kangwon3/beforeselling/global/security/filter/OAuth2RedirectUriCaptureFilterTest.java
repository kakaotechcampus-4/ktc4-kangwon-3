package kakaotech.kangwon3.beforeselling.global.security.filter;

import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OAuth2RedirectUriCaptureFilterTest {

    private static final String LOGIN_START_URI = "/oauth2/authorization/kakao";
    private static final String ALLOWED_REDIRECT_URI = "http://localhost:5173/oauth/callback";

    private final AppProperties appProperties = new AppProperties(
            new AppProperties.Cors(List.of()),
            new AppProperties.OAuth2(List.of(ALLOWED_REDIRECT_URI)),
            new AppProperties.Cookie(false, "Lax"));
    private final OAuth2RedirectCookieProvider cookieProvider = new OAuth2RedirectCookieProvider(appProperties);
    private final OAuth2RedirectUriCaptureFilter filter = new OAuth2RedirectUriCaptureFilter(
            PathPatternRequestMatcher.pathPattern("/oauth2/authorization/*"), appProperties, cookieProvider);

    private final MockHttpServletResponse response = new MockHttpServletResponse();
    private final MockFilterChain filterChain = new MockFilterChain();

    @Test
    @DisplayName("허용 목록에 있는 redirect_uri면 쿠키에 담고 다음 필터로 넘긴다.")
    void doFilter_withAllowedRedirectUri_thenSaveCookie() throws Exception {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest("GET", LOGIN_START_URI);
        request.setParameter("redirect_uri", ALLOWED_REDIRECT_URI);

        // when
        filter.doFilter(request, response, filterChain);

        // then
        assertThat(response.getHeader(HttpHeaders.SET_COOKIE))
                .contains(OAuth2RedirectCookieProvider.COOKIE_NAME + "=" + ALLOWED_REDIRECT_URI);
        assertThat(filterChain.getRequest()).isSameAs(request);
    }

    @ParameterizedTest
    @ValueSource(strings = {"https://evil.example.com/callback", "", "   "})
    @DisplayName("허용 목록에 없거나 빈 redirect_uri면 쿠키를 만들지 않고 다음 필터로 넘긴다.")
    void doFilter_withInvalidRedirectUri_thenSkipCookie(String redirectUri) throws Exception {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest("GET", LOGIN_START_URI);
        request.setParameter("redirect_uri", redirectUri);

        // when
        filter.doFilter(request, response, filterChain);

        // then
        assertThat(response.getHeader(HttpHeaders.SET_COOKIE)).isNull();
        assertThat(filterChain.getRequest()).isSameAs(request);
    }

    @Test
    @DisplayName("redirect_uri가 없으면 쿠키를 만들지 않고 다음 필터로 넘긴다.")
    void doFilter_withoutRedirectUri_thenSkipCookie() throws Exception {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest("GET", LOGIN_START_URI);

        // when
        filter.doFilter(request, response, filterChain);

        // then
        assertThat(response.getHeader(HttpHeaders.SET_COOKIE)).isNull();
        assertThat(filterChain.getRequest()).isSameAs(request);
    }

    @Test
    @DisplayName("소셜 로그인 시작 요청이 아니면 허용된 redirect_uri가 있어도 쿠키를 만들지 않는다.")
    void doFilter_withOtherPath_thenSkipCookie() throws Exception {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/v1/diagnoses");
        request.setParameter("redirect_uri", ALLOWED_REDIRECT_URI);

        // when
        filter.doFilter(request, response, filterChain);

        // then
        assertThat(response.getHeader(HttpHeaders.SET_COOKIE)).isNull();
        assertThat(filterChain.getRequest()).isSameAs(request);
    }
}
