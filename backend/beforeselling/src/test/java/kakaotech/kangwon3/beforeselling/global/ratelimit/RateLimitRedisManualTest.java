package kakaotech.kangwon3.beforeselling.global.ratelimit;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 로컬 Redis(localhost:6379)로 Bucket4j Lettuce 연동을 확인하는 수동 테스트.
 * RATE_LIMIT_REDIS_TEST 가 없으면 건너뛰므로 CI 와 평소 테스트에서는 실행되지 않는다.
 *
 * 실행: RATE_LIMIT_REDIS_TEST=1 ./gradlew test --tests '*RateLimitRedisManualTest'
 */
@SpringBootTest(properties = "rate-limit.ai.capacity=2")
@ActiveProfiles("test")
@EnabledIfEnvironmentVariable(named = "RATE_LIMIT_REDIS_TEST", matches = ".+")
class RateLimitRedisManualTest {

    @Autowired
    private RateLimiter rateLimiter;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @Test
    @DisplayName("Redis에 사용자별 버킷을 만들어 한도를 넘는 요청을 막고, 버킷 키에는 만료 시간이 걸린다")
    void limitsRequestsWithRedisBucket() {
        // given
        UUID userId = UUID.randomUUID();
        String key = "rate_limit:ai:" + userId;
        rateLimiter.tryConsume(RateLimitPolicy.AI, userId);
        rateLimiter.tryConsume(RateLimitPolicy.AI, userId);

        // when
        RateLimitResult result = rateLimiter.tryConsume(RateLimitPolicy.AI, userId);

        // then
        assertThat(result.allowed()).isFalse();
        assertThat(result.retryAfterSeconds()).isBetween(1L, 30L);
        assertThat(redisTemplate.hasKey(key)).isTrue();
        assertThat(redisTemplate.getExpire(key)).isPositive();

        redisTemplate.delete(key);
    }
}
