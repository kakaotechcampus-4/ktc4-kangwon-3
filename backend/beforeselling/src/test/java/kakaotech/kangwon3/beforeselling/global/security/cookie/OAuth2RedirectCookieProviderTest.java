package kakaotech.kangwon3.beforeselling.global.security.cookie;

import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class OAuth2RedirectCookieProviderTest {

    private static final String DEFAULT_REDIRECT_URI = "http://localhost:5173/oauth/callback";
    private static final String OTHER_ALLOWED_REDIRECT_URI = "https://palgijeone.com/oauth/callback";

    private final OAuth2RedirectCookieProvider cookieProvider = new OAuth2RedirectCookieProvider(new AppProperties(
            new AppProperties.Cors(List.of()),
            new AppProperties.OAuth2(List.of(DEFAULT_REDIRECT_URI, OTHER_ALLOWED_REDIRECT_URI)),
            new AppProperties.Cookie(true, "Lax")));

    @Test
    @DisplayName("리다이렉트 쿠키를 만들면 HttpOnly·Secure·SameSite가 설정되고 5분 뒤 만료된다.")
    void create_thenSecureCookieExpiresIn5Minutes() {
        // when
        ResponseCookie cookie = cookieProvider.create(OTHER_ALLOWED_REDIRECT_URI);

        // then
        assertThat(cookie.getName()).isEqualTo(OAuth2RedirectCookieProvider.COOKIE_NAME);
        assertThat(cookie.getValue()).isEqualTo(OTHER_ALLOWED_REDIRECT_URI);
        assertThat(cookie.isHttpOnly()).isTrue();
        assertThat(cookie.isSecure()).isTrue();
        assertThat(cookie.getSameSite()).isEqualTo("Lax");
        assertThat(cookie.getPath()).isEqualTo("/");
        assertThat(cookie.getMaxAge()).isEqualTo(Duration.ofMinutes(5));
    }

    @Test
    @DisplayName("만료 쿠키는 값이 비어 있고 즉시 만료된다.")
    void expire_thenEmptyValueAndZeroMaxAge() {
        // when
        ResponseCookie cookie = cookieProvider.expire();

        // then
        assertThat(cookie.getName()).isEqualTo(OAuth2RedirectCookieProvider.COOKIE_NAME);
        assertThat(cookie.getValue()).isEmpty();
        assertThat(cookie.getMaxAge()).isEqualTo(Duration.ZERO);
    }

    @Test
    @DisplayName("쿠키 값이 허용 목록에 있으면 그 주소로 리다이렉트한다.")
    void resolveRedirectUri_withAllowedCookie_thenCookieValue() {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setCookies(new Cookie(OAuth2RedirectCookieProvider.COOKIE_NAME, OTHER_ALLOWED_REDIRECT_URI));

        // when
        String redirectUri = cookieProvider.resolveRedirectUri(request);

        // then
        assertThat(redirectUri).isEqualTo(OTHER_ALLOWED_REDIRECT_URI);
    }

    @Test
    @DisplayName("쿠키 값이 허용 목록에 없으면(위변조) 기본 주소로 리다이렉트한다.")
    void resolveRedirectUri_withNotAllowedCookie_thenDefault() {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setCookies(new Cookie(OAuth2RedirectCookieProvider.COOKIE_NAME, "https://evil.example.com/callback"));

        // when
        String redirectUri = cookieProvider.resolveRedirectUri(request);

        // then
        assertThat(redirectUri).isEqualTo(DEFAULT_REDIRECT_URI);
    }

    @Test
    @DisplayName("쿠키가 없으면(만료·미설정) 기본 주소로 리다이렉트한다.")
    void resolveRedirectUri_withoutCookie_thenDefault() {
        // given
        MockHttpServletRequest request = new MockHttpServletRequest();

        // when
        String redirectUri = cookieProvider.resolveRedirectUri(request);

        // then
        assertThat(redirectUri).isEqualTo(DEFAULT_REDIRECT_URI);
    }

    @Test
    @DisplayName("쿠키를 추가하면 Set-Cookie 헤더로 내려간다.")
    void addCookie_thenSetCookieHeader() {
        // given
        MockHttpServletResponse response = new MockHttpServletResponse();
        ResponseCookie cookie = cookieProvider.create(DEFAULT_REDIRECT_URI);

        // when
        cookieProvider.addCookie(response, cookie);

        // then
        assertThat(response.getHeader(HttpHeaders.SET_COOKIE))
                .startsWith(OAuth2RedirectCookieProvider.COOKIE_NAME + "=" + DEFAULT_REDIRECT_URI)
                .contains("HttpOnly");
    }
}
