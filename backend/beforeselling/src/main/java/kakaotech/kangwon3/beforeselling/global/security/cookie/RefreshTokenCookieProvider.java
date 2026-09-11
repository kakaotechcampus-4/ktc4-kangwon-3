package kakaotech.kangwon3.beforeselling.global.security.cookie;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;
import org.springframework.web.util.WebUtils;

import java.time.Duration;
import java.util.Optional;

/**
 * 리프레시 토큰 쿠키 생성/만료/조회.
 * HttpOnly로 스크립트 접근을 차단하고, Path를 인증 API 경로로 제한해 다른 요청에는 쿠키가 실리지 않도록 합니다.
 */
@Component
@RequiredArgsConstructor
public class RefreshTokenCookieProvider {

    public static final String COOKIE_NAME = "refresh_token";
    public static final String COOKIE_PATH = "/api/v1/auth";

    private final AppProperties appProperties;
    private final JwtProperties jwtProperties;

    public ResponseCookie create(String refreshToken) {
        return build(refreshToken, jwtProperties.refreshTokenExpiration());
    }

    public ResponseCookie expire() {
        return build("", Duration.ZERO);
    }

    public Optional<String> read(HttpServletRequest request) {
        return Optional.ofNullable(WebUtils.getCookie(request, COOKIE_NAME))
                .map(Cookie::getValue);
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
                .path(COOKIE_PATH)
                .maxAge(maxAge)
                .build();
    }
}
