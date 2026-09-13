package kakaotech.kangwon3.beforeselling.global.security.oauth2.handler;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.Authentication;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.IOException;

/**
 * 소셜 로그인 성공 시 토큰 쌍을 발급하고, 리프레시 토큰만 HttpOnly 쿠키로 심은 뒤 프론트엔드로 리다이렉트합니다.
 * 액세스 토큰은 URL에 노출하지 않으며, 프론트엔드가 이어서 POST /api/v1/auth/reissue 로 획득합니다.
 * 신규 가입 여부는 {@code isNewUser} 쿼리 파라미터로 전달합니다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OAuth2SuccessHandler implements AuthenticationSuccessHandler {

    private static final String IS_NEW_USER_PARAM = "isNewUser";

    private final AuthTokenService authTokenService;
    private final RefreshTokenCookieProvider refreshTokenCookieProvider;
    private final AppProperties appProperties;

    @Override
    public void onAuthenticationSuccess(HttpServletRequest request, HttpServletResponse response,
                                        Authentication authentication) throws IOException {
        CustomOAuth2User principal = (CustomOAuth2User) authentication.getPrincipal();

        TokenPair tokenPair = authTokenService.issueTokens(principal.userId(), principal.role());
        refreshTokenCookieProvider.addCookie(response, refreshTokenCookieProvider.create(tokenPair.refreshToken()));

        log.debug("소셜 로그인 성공. userId={}, isNewUser={}", principal.userId(), principal.isNewUser());

        String redirectUri = UriComponentsBuilder.fromUriString(appProperties.oauth2().frontendRedirectUri())
                .queryParam(IS_NEW_USER_PARAM, principal.isNewUser())
                .build()
                .toUriString();
        response.sendRedirect(redirectUri);
    }
}
