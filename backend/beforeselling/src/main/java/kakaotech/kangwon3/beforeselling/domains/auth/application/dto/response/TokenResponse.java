package kakaotech.kangwon3.beforeselling.domains.auth.application.dto.response;

import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;

/**
 * 액세스 토큰 응답. 리프레시 토큰은 바디에 포함하지 않고 HttpOnly 쿠키로만 전달합니다.
 *
 * @param expiresIn 액세스 토큰 유효 시간(초)
 */
public record TokenResponse(
        String accessToken,
        String tokenType,
        long expiresIn
) {

    private static final String BEARER = "Bearer";

    public static TokenResponse from(TokenPair tokenPair) {
        return new TokenResponse(tokenPair.accessToken(), BEARER, tokenPair.accessTokenExpiresIn());
    }
}
