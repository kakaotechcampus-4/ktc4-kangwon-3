package kakaotech.kangwon3.beforeselling.domains.auth.domain.service;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenClaims;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenType;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 토큰 쌍 발급/재발급/폐기의 단일 진입점.
 * 소셜 로그인 성공 핸들러(발급)와 인증 API(재발급/로그아웃)가 공통으로 사용합니다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthTokenService {

    private final JwtProvider jwtProvider;
    private final RefreshTokenService refreshTokenService;
    private final UserService userService;

    public TokenPair issueTokens(Long userId, Role role) {
        TokenPair tokenPair = jwtProvider.issueTokenPair(userId, role);
        refreshTokenService.saveRefreshToken(
                tokenPair.refreshTokenJti(), userId, jwtProvider.getRefreshTokenExpiration());
        return tokenPair;
    }

    /**
     * 리프레시 토큰으로 새 토큰 쌍을 발급합니다. 매 재발급마다 기존 리프레시 토큰은 폐기됩니다(rotation).
     * 사용자 정보는 DB에서 다시 읽어 역할 변경/탈퇴를 반영합니다.
     */
    public TokenPair reissueTokens(String refreshToken) {
        TokenClaims claims = jwtProvider.parse(refreshToken, TokenType.REFRESH);
        refreshTokenService.validateRefreshToken(claims.jti(), claims.userId());

        User user = userService.getUser(claims.userId());

        refreshTokenService.removeRefreshToken(claims.jti());
        return issueTokens(user.getId(), user.getRole());
    }

    /**
     * 리프레시 토큰을 폐기합니다. 이미 만료/변조된 토큰이어도 로그아웃 자체는 성공 처리합니다.
     */
    public void removeRefreshToken(String refreshToken) {
        if (refreshToken == null || refreshToken.isBlank()) {
            return;
        }
        try {
            TokenClaims claims = jwtProvider.parse(refreshToken, TokenType.REFRESH);
            refreshTokenService.removeRefreshToken(claims.jti());
        } catch (BaseException e) {
            log.debug("로그아웃 시 유효하지 않은 리프레시 토큰은 무시합니다. code={}", e.getResponseCode().getCode());
        }
    }
}
