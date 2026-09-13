package kakaotech.kangwon3.beforeselling.domains.auth.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
@RequiredArgsConstructor
public class AuthUseCase {

    private final AuthTokenService authTokenService;

    /**
     * 리프레시 토큰으로 새 토큰 쌍을 발급합니다. 쿠키가 없으면 재로그인이 필요하다는 의미로 INVALID_REFRESH_TOKEN을 반환합니다.
     */
    public TokenPair reissueToken(String refreshToken) {
        if (!StringUtils.hasText(refreshToken)) {
            throw new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN);
        }
        return authTokenService.reissueTokens(refreshToken);
    }

    public void logout(String refreshToken) {
        authTokenService.removeRefreshToken(refreshToken);
    }
}
