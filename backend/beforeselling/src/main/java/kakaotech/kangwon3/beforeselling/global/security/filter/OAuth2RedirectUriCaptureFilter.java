package kakaotech.kangwon3.beforeselling.global.security.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import lombok.RequiredArgsConstructor;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 소셜 로그인 시작 요청(/oauth2/authorization/{registrationId}?redirect_uri=...)에서
 * 프론트엔드가 지정한 콜백 주소를 읽어 허용 목록(app.oauth2.allowed-redirect-uris)과 대조한 뒤
 * 짧은 쿠키에 담아둡니다. OAuth2SuccessHandler/OAuth2FailureHandler가 콜백 시점에 이 쿠키를 읽어
 * 최종 리다이렉트 대상으로 사용합니다.
 * 파라미터가 없거나 허용 목록에 없는 값이면 무시하고, 핸들러는 첫 번째 허용 값(기본값)으로 리다이렉트합니다.
 */
@RequiredArgsConstructor
public class OAuth2RedirectUriCaptureFilter extends OncePerRequestFilter {

    private static final String REDIRECT_URI_PARAM = "redirect_uri";

    private final RequestMatcher matcher;
    private final AppProperties appProperties;
    private final OAuth2RedirectCookieProvider cookieProvider;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !matcher.matches(request);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String requestedRedirectUri = request.getParameter(REDIRECT_URI_PARAM);

        if (StringUtils.hasText(requestedRedirectUri)
                && appProperties.oauth2().allowedRedirectUris().contains(requestedRedirectUri)) {
            cookieProvider.addCookie(response, cookieProvider.create(requestedRedirectUri));
        }

        filterChain.doFilter(request, response);
    }
}
