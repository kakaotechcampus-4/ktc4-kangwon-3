package kakaotech.kangwon3.beforeselling.global.ratelimit;

import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties.Limit;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class RateLimiterTest {

    private final RateLimitProperties properties = new RateLimitProperties(
            new Limit(3, Duration.ofMinutes(1)),
            new Limit(2, Duration.ofMinutes(1))
    );
    private final RateLimiter rateLimiter = new RateLimiter(new InMemoryProxyManager(), properties);

    @Test
    @DisplayName("한도까지는 요청을 허용하고, 한도를 넘는 요청은 막으며 다시 시도할 수 있을 때까지 남은 초를 알려준다")
    void rejectsRequestOverLimitWithRetryAfter() {
        // given
        UUID userId = UUID.randomUUID();
        rateLimiter.tryConsume(RateLimitPolicy.AI, userId);
        RateLimitResult second = rateLimiter.tryConsume(RateLimitPolicy.AI, userId);

        // when
        RateLimitResult third = rateLimiter.tryConsume(RateLimitPolicy.AI, userId);

        // then
        assertThat(second.allowed()).isTrue();
        assertThat(third.allowed()).isFalse();
        // 1분에 2개를 채우므로 다음 토큰은 30초 뒤에 생긴다
        assertThat(third.retryAfterSeconds()).isEqualTo(30);
    }

    @Test
    @DisplayName("다른 사용자의 요청은 한도를 따로 센다")
    void countsEachUserSeparately() {
        // given
        UUID exhaustedUser = UUID.randomUUID();
        rateLimiter.tryConsume(RateLimitPolicy.AI, exhaustedUser);
        rateLimiter.tryConsume(RateLimitPolicy.AI, exhaustedUser);

        // when
        RateLimitResult result = rateLimiter.tryConsume(RateLimitPolicy.AI, UUID.randomUUID());

        // then
        assertThat(rateLimiter.tryConsume(RateLimitPolicy.AI, exhaustedUser).allowed()).isFalse();
        assertThat(result.allowed()).isTrue();
    }

    @Test
    @DisplayName("같은 사용자라도 AI 한도를 다 쓴 것은 기본 한도에 영향을 주지 않는다")
    void countsEachPolicySeparately() {
        // given
        UUID userId = UUID.randomUUID();
        rateLimiter.tryConsume(RateLimitPolicy.AI, userId);
        rateLimiter.tryConsume(RateLimitPolicy.AI, userId);

        // when
        RateLimitResult result = rateLimiter.tryConsume(RateLimitPolicy.DEFAULT, userId);

        // then
        assertThat(rateLimiter.tryConsume(RateLimitPolicy.AI, userId).allowed()).isFalse();
        assertThat(result.allowed()).isTrue();
    }
}
