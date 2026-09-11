package kakaotech.kangwon3.beforeselling.global.security.jwt;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JwtProviderTest {

    private static final String SECRET = "test-jwt-secret-key-must-be-at-least-32-bytes-long-0123456789";
    private static final String OTHER_SECRET = "another-jwt-secret-key-that-is-also-long-enough-9876543210";

    private JwtProvider jwtProvider;

    @BeforeEach
    void setUp() {
        jwtProvider = new JwtProvider(new JwtProperties(SECRET, Duration.ofMinutes(30), Duration.ofDays(14)));
    }

    @Test
    @DisplayName("액세스 토큰을 발급하면 사용자 ID와 역할을 다시 읽어낼 수 있다.")
    void issueAccessToken_thenParseClaims() {
        // given
        Long userId = 1L;

        // when
        TokenPair tokenPair = jwtProvider.issueTokenPair(userId, Role.USER);
        TokenClaims claims = jwtProvider.parse(tokenPair.accessToken(), TokenType.ACCESS);

        // then
        assertThat(claims.userId()).isEqualTo(userId);
        assertThat(claims.role()).isEqualTo(Role.USER);
        assertThat(claims.type()).isEqualTo(TokenType.ACCESS);
        assertThat(tokenPair.accessTokenExpiresIn()).isEqualTo(Duration.ofMinutes(30).toSeconds());
    }

    @Test
    @DisplayName("리프레시 토큰에는 고유한 jti가 포함되고 토큰 쌍의 jti와 일치한다.")
    void issueRefreshToken_thenJtiMatches() {
        // given & when
        TokenPair tokenPair = jwtProvider.issueTokenPair(1L, Role.USER);
        TokenClaims claims = jwtProvider.parse(tokenPair.refreshToken(), TokenType.REFRESH);

        // then
        assertThat(claims.jti()).isNotBlank();
        assertThat(claims.jti()).isEqualTo(tokenPair.refreshTokenJti());
    }

    @Test
    @DisplayName("만료된 액세스 토큰을 검증하면 EXPIRED_ACCESS_TOKEN 예외가 발생한다.")
    void parseExpiredAccessToken_thenThrowExpired() {
        // given
        JwtProvider expiredProvider = new JwtProvider(
                new JwtProperties(SECRET, Duration.ofSeconds(-1), Duration.ofDays(14)));
        TokenPair tokenPair = expiredProvider.issueTokenPair(1L, Role.USER);

        // when & then
        assertThatThrownBy(() -> jwtProvider.parse(tokenPair.accessToken(), TokenType.ACCESS))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.EXPIRED_ACCESS_TOKEN);
    }

    @Test
    @DisplayName("만료된 리프레시 토큰을 검증하면 INVALID_REFRESH_TOKEN 예외가 발생한다.")
    void parseExpiredRefreshToken_thenThrowInvalidRefresh() {
        // given
        JwtProvider expiredProvider = new JwtProvider(
                new JwtProperties(SECRET, Duration.ofMinutes(30), Duration.ofSeconds(-1)));
        TokenPair tokenPair = expiredProvider.issueTokenPair(1L, Role.USER);

        // when & then
        assertThatThrownBy(() -> jwtProvider.parse(tokenPair.refreshToken(), TokenType.REFRESH))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_REFRESH_TOKEN);
    }

    @Test
    @DisplayName("리프레시 토큰을 액세스 토큰으로 검증하면 INVALID_ACCESS_TOKEN 예외가 발생한다.")
    void parseRefreshTokenAsAccess_thenThrowInvalidAccess() {
        // given
        TokenPair tokenPair = jwtProvider.issueTokenPair(1L, Role.USER);

        // when & then
        assertThatThrownBy(() -> jwtProvider.parse(tokenPair.refreshToken(), TokenType.ACCESS))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_ACCESS_TOKEN);
    }

    @Test
    @DisplayName("다른 키로 서명된 토큰을 검증하면 INVALID_ACCESS_TOKEN 예외가 발생한다.")
    void parseTokenSignedWithOtherKey_thenThrowInvalidAccess() {
        // given
        JwtProvider otherProvider = new JwtProvider(
                new JwtProperties(OTHER_SECRET, Duration.ofMinutes(30), Duration.ofDays(14)));
        TokenPair tokenPair = otherProvider.issueTokenPair(1L, Role.USER);

        // when & then
        assertThatThrownBy(() -> jwtProvider.parse(tokenPair.accessToken(), TokenType.ACCESS))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_ACCESS_TOKEN);
    }

    @Test
    @DisplayName("형식이 올바르지 않은 문자열을 검증하면 INVALID_ACCESS_TOKEN 예외가 발생한다.")
    void parseMalformedToken_thenThrowInvalidAccess() {
        assertThatThrownBy(() -> jwtProvider.parse("not.a.jwt", TokenType.ACCESS))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_ACCESS_TOKEN);
    }

    @Test
    @DisplayName("role 클레임이 알 수 없는 값이면 서명이 유효해도 INVALID_ACCESS_TOKEN 예외가 발생한다.")
    void parseTokenWithUnknownRoleClaim_thenThrowInvalidAccess() {
        // given: 우리 서명 키로 만들었지만 role 클레임이 존재하지 않는 값인 토큰 (예: enum 상수 삭제/변경 후 남은 구 토큰을 흉내)
        String token = tokenWithRawRoleClaim("SUPER_ADMIN");

        // when & then
        assertThatThrownBy(() -> jwtProvider.parse(token, TokenType.ACCESS))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_ACCESS_TOKEN);
    }

    private String tokenWithRawRoleClaim(String rawRole) {
        SecretKey key = Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8));
        Instant now = Instant.now();

        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject("1")
                .claim("role", rawRole)
                .claim("type", TokenType.ACCESS.name())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(Duration.ofMinutes(30))))
                .signWith(key)
                .compact();
    }
}
