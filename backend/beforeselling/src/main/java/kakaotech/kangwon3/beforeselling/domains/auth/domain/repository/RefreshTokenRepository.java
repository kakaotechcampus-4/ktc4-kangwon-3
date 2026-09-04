package kakaotech.kangwon3.beforeselling.domains.auth.domain.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.util.Optional;

/**
 * 리프레시 토큰 저장소 (Redis).
 * key: refresh_token:{jti}, value: userId, TTL: 리프레시 토큰 만료 시간
 */
@Repository
@RequiredArgsConstructor
public class RefreshTokenRepository {

    private static final String KEY_PREFIX = "refresh_token:";

    private final StringRedisTemplate redisTemplate;

    public void insertRefreshToken(String jti, Long userId, Duration ttl) {
        redisTemplate.opsForValue().set(keyOf(jti), String.valueOf(userId), ttl);
    }

    public Optional<Long> findUserIdByJti(String jti) {
        return Optional.ofNullable(redisTemplate.opsForValue().get(keyOf(jti)))
                .map(Long::valueOf);
    }

    public void deleteRefreshToken(String jti) {
        redisTemplate.delete(keyOf(jti));
    }

    private String keyOf(String jti) {
        return KEY_PREFIX + jti;
    }
}
