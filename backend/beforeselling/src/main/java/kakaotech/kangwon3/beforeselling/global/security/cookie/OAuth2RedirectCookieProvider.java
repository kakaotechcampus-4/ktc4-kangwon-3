package kakaotech.kangwon3.beforeselling.global.security.cookie;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;
import org.springframework.web.util.WebUtils;

import java.time.Duration;
import java.util.Optional;

/**
 * 소셜 로그인 시작 시점에 요청한 프론트엔드 콜백 주소를, 콜백(성공/실패) 시점까지 짧게 들고 가기 위한 쿠키.
 * app.oauth2.allowed-redirect-uris 허용 목록에 있는 값만 필터에서 이 쿠키에 담기므로,
 * 핸들러 쪽에서도 다시 한 번 허용 목록과 대조한 뒤에만 리다이렉트 대상으로 사용해야 합니다(오픈 리다이렉트 방지).
 */
@Component
@RequiredArgsConstructor
public class OAuth2RedirectCookieProvider {

    public static final String COOKIE_NAME = "oauth2_redirect_uri";
    private static final Duration MAX_AGE = Duration.ofMinutes(5);

    private final AppProperties appProperties;

    public ResponseCookie create(String redirectUri) {
        return build(redirectUri, MAX_AGE);
    }

    public ResponseCookie expire() {
        return build("", Duration.ZERO);
    }

    public Optional<String> read(HttpServletRequest request) {
        return Optional.ofNullable(WebUtils.getCookie(request, COOKIE_NAME))
                .map(Cookie::getValue);
    }

    /**
     * 콜백 시점에 사용할 프론트엔드 리다이렉트 주소를 결정합니다.
     * 쿠키 값이 허용 목록에 없으면(만료, 위변조, 미존재 등) 목록의 첫 번째 값을 기본값으로 사용합니다.
     */
    public String resolveRedirectUri(HttpServletRequest request) {
        var allowedRedirectUris = appProperties.oauth2().allowedRedirectUris();
        return read(request)
                .filter(allowedRedirectUris::contains)
                .orElseGet(allowedRedirectUris::getFirst);
    }

    public void addCookie(HttpServletResponse response, ResponseCookie cookie) {
        response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
    }

    private ResponseCookie build(String value, Duration maxAge) {
        AppProperties.Cookie cookieProperties = appProperties.cookie();

        return ResponseCookie.from(COOKIE_NAME, value)
                .httpOnly(true)
                .secure(cookieProperties.secure())
                .sameSite(cookieProperties.sameSite())
                .path("/")
                .maxAge(maxAge)
                .build();
    }
}
