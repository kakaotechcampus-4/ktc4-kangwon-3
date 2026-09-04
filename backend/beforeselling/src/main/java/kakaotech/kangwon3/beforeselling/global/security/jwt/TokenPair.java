package kakaotech.kangwon3.beforeselling.global.security.jwt;

/**
 * 함께 발급된 액세스/리프레시 토큰 쌍.
 *
 * @param refreshTokenJti        리프레시 토큰의 jti (Redis 저장 키로 사용)
 * @param accessTokenExpiresIn   액세스 토큰 유효 시간(초)
 */
public record TokenPair(
        String accessToken,
        String refreshToken,
        String refreshTokenJti,
        long accessTokenExpiresIn
) {
}
