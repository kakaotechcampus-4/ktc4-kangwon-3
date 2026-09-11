package kakaotech.kangwon3.beforeselling.domains.auth.presentation.controller;

import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.domains.auth.application.dto.response.TokenResponse;
import kakaotech.kangwon3.beforeselling.domains.auth.application.usecase.AuthUseCase;
import kakaotech.kangwon3.beforeselling.domains.auth.presentation.api.AuthApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 인증 API.
 * 소셜 로그인 시작은 Spring Security가 제공하는 GET /oauth2/authorization/{kakao|naver|google} 를 사용합니다.
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController implements AuthApi {

    private final AuthUseCase authUseCase;
    private final RefreshTokenCookieProvider refreshTokenCookieProvider;

    /**
     * 리프레시 토큰(쿠키)으로 액세스 토큰을 재발급합니다. 리프레시 토큰도 함께 회전되어 새 쿠키로 내려갑니다.
     * 소셜 로그인 직후 프론트엔드가 액세스 토큰을 처음 획득하는 용도로도 사용됩니다.
     */
    @Override
    @PostMapping("/reissue")
    public ResponseEntity<ApiResponse<TokenResponse>> reissueToken(
            @CookieValue(name = RefreshTokenCookieProvider.COOKIE_NAME, required = false) String refreshToken,
            HttpServletResponse response
    ) {
        TokenPair tokenPair = authUseCase.reissueToken(refreshToken);
        refreshTokenCookieProvider.addCookie(response, refreshTokenCookieProvider.create(tokenPair.refreshToken()));

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK, TokenResponse.from(tokenPair)));
    }

    /**
     * 리프레시 토큰을 폐기하고 쿠키를 만료시킵니다.
     */
    @Override
    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Void>> logout(
            @LoginUser UserPrincipal principal,
            @CookieValue(name = RefreshTokenCookieProvider.COOKIE_NAME, required = false) String refreshToken,
            HttpServletResponse response
    ) {
        authUseCase.logout(refreshToken);
        refreshTokenCookieProvider.addCookie(response, refreshTokenCookieProvider.expire());

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
    }
}
