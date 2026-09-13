package kakaotech.kangwon3.beforeselling.global.security.jwt;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

@Component
public class JwtProvider {

    private static final String CLAIM_ROLE = "role";
    private static final String CLAIM_TYPE = "type";

    private final SecretKey secretKey;
    private final Duration accessTokenExpiration;
    private final Duration refreshTokenExpiration;

    public JwtProvider(JwtProperties jwtProperties) {
        this.secretKey = Keys.hmacShaKeyFor(jwtProperties.secret().getBytes(StandardCharsets.UTF_8));
        this.accessTokenExpiration = jwtProperties.accessTokenExpiration();
        this.refreshTokenExpiration = jwtProperties.refreshTokenExpiration();
    }

    public TokenPair issueTokenPair(Long userId, Role role) {
        String accessToken = generateToken(userId, role, TokenType.ACCESS, UUID.randomUUID().toString(), accessTokenExpiration);
        String refreshTokenJti = UUID.randomUUID().toString();
        String refreshToken = generateToken(userId, role, TokenType.REFRESH, refreshTokenJti, refreshTokenExpiration);

        return new TokenPair(accessToken, refreshToken, refreshTokenJti, accessTokenExpiration.toSeconds());
    }

    /**
     * 토큰의 서명/만료를 검증하고 기대한 타입(ACCESS/REFRESH)과 일치하는지 확인합니다.
     * 타입을 검증하지 않으면 리프레시 토큰을 Authorization 헤더에 실어 액세스 토큰처럼 사용할 수 있으므로 반드시 검사합니다.
     */
    public TokenClaims parse(String token, TokenType expectedType) {
        Claims claims = parseClaims(token, expectedType);
        TokenType actualType = resolveType(claims, expectedType);

        if (actualType != expectedType) {
            throw new BaseException(invalidCodeOf(expectedType));
        }

        return new TokenClaims(
                Long.parseLong(claims.getSubject()),
                resolveRole(claims, expectedType),
                actualType,
                claims.getId()
        );
    }

    public Duration getRefreshTokenExpiration() {
        return refreshTokenExpiration;
    }

    private String generateToken(Long userId, Role role, TokenType type,
                                 String jti, Duration expiration) {
        Instant now = Instant.now();

        return Jwts.builder()
                .id(jti)
                .subject(String.valueOf(userId))
                .claim(CLAIM_ROLE, role.name())
                .claim(CLAIM_TYPE, type.name())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(expiration)))
                .signWith(secretKey)
                .compact();
    }

    private Claims parseClaims(String token, TokenType expectedType) {
        try {
            return Jwts.parser()
                    .verifyWith(secretKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        } catch (ExpiredJwtException e) {
            throw new BaseException(expiredCodeOf(expectedType));
        } catch (JwtException | IllegalArgumentException e) {
            throw new BaseException(invalidCodeOf(expectedType));
        }
    }

    private TokenType resolveType(Claims claims, TokenType expectedType) {
        try {
            return TokenType.valueOf(claims.get(CLAIM_TYPE, String.class));
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new BaseException(invalidCodeOf(expectedType));
        }
    }

    private Role resolveRole(Claims claims, TokenType expectedType) {
        try {
            return Role.valueOf(claims.get(CLAIM_ROLE, String.class));
        } catch (IllegalArgumentException | NullPointerException e) {
            throw new BaseException(invalidCodeOf(expectedType));
        }
    }

    private AuthResponseCode expiredCodeOf(TokenType type) {
        return type == TokenType.ACCESS
                ? AuthResponseCode.EXPIRED_ACCESS_TOKEN
                : AuthResponseCode.INVALID_REFRESH_TOKEN;
    }

    private AuthResponseCode invalidCodeOf(TokenType type) {
        return type == TokenType.ACCESS
                ? AuthResponseCode.INVALID_ACCESS_TOKEN
                : AuthResponseCode.INVALID_REFRESH_TOKEN;
    }
}
