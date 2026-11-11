package kakaotech.kangwon3.beforeselling.domains.auth.domain.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.util.UUID;

/**
 * 탈퇴 회원 블랙리스트 (Redis).
 * key: withdrawn_user:{userId}, TTL: 액세스 토큰 만료 시간
 */
@Repository
@RequiredArgsConstructor
public class WithdrawnUserRepository {

    private static final String KEY_PREFIX = "withdrawn_user:";
    private static final String VALUE = "1";

    private final StringRedisTemplate redisTemplate;

    public void insertWithdrawnUser(UUID userId, Duration ttl) {
        redisTemplate.opsForValue().set(keyOf(userId), VALUE, ttl);
    }

    public boolean existsByUserId(UUID userId) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(keyOf(userId)));
    }

    private String keyOf(UUID userId) {
        return KEY_PREFIX + userId;
    }
}
