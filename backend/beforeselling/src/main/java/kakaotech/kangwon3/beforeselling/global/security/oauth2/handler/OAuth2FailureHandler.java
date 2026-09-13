package kakaotech.kangwon3.beforeselling.global.security.oauth2.handler;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.authentication.AuthenticationFailureHandler;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.IOException;

/**
 * 소셜 로그인 실패 시 프론트엔드 콜백 URL로 에러 코드를 쿼리 파라미터에 담아 리다이렉트합니다.
 * 예: http://localhost:5173/oauth/callback?error=AUTH-004
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OAuth2FailureHandler implements AuthenticationFailureHandler {

    private static final String ERROR_PARAM = "error";

    private final AppProperties appProperties;

    @Override
    public void onAuthenticationFailure(HttpServletRequest request, HttpServletResponse response,
                                        AuthenticationException exception) throws IOException {
        String errorCode = resolveErrorCode(exception);
        log.warn("소셜 로그인 실패. code={}, message={}", errorCode, exception.getMessage());

        String redirectUri = UriComponentsBuilder.fromUriString(appProperties.oauth2().frontendRedirectUri())
                .queryParam(ERROR_PARAM, errorCode)
                .build()
                .toUriString();
        response.sendRedirect(redirectUri);
    }

    private String resolveErrorCode(AuthenticationException exception) {
        // CustomOAuth2UserService에서 BaseException을 감싸 던진 경우 해당 코드를 그대로 전달
        if (exception.getCause() instanceof BaseException baseException) {
            return baseException.getResponseCode().getCode();
        }
        return AuthResponseCode.OAUTH2_LOGIN_FAILED.getCode();
    }
}
