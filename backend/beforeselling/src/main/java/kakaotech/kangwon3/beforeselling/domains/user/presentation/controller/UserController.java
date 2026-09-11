package kakaotech.kangwon3.beforeselling.domains.user.presentation.controller;

import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.domains.user.application.usecase.UserWithdrawalUseCase;
import kakaotech.kangwon3.beforeselling.domains.user.presentation.api.UserApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Slf4j
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController implements UserApi {

    private final UserWithdrawalUseCase userWithdrawalUseCase;
    private final RefreshTokenCookieProvider refreshTokenCookieProvider;

    /**
     * 회원 탈퇴. 회원 정보를 삭제하고 현재 리프레시 토큰 쿠키를 만료시킵니다.
     */
    @Override
    @DeleteMapping("/me")
    public ResponseEntity<ApiResponse<Void>> withdraw(
            @LoginUser UserPrincipal principal,
            @CookieValue(name = RefreshTokenCookieProvider.COOKIE_NAME, required = false) String refreshToken,
            HttpServletResponse response
    ) {
        userWithdrawalUseCase.withdraw(principal.userId(), refreshToken);
        refreshTokenCookieProvider.addCookie(response, refreshTokenCookieProvider.expire());

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
    }
}
