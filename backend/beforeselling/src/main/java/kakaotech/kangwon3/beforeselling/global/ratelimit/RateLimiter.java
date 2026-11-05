package kakaotech.kangwon3.beforeselling.global.ratelimit;

import io.github.bucket4j.BucketConfiguration;
import io.github.bucket4j.ConsumptionProbe;
import io.github.bucket4j.distributed.proxy.ProxyManager;
import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties.Limit;
import lombok.RequiredArgsConstructor;

import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 사용자·정책별 토큰 버킷.
 * key: rate_limit:{policy}:{userId}
 */
@RequiredArgsConstructor
public class RateLimiter {

    private static final String KEY_PREFIX = "rate_limit:";

    private final ProxyManager<String> proxyManager;
    private final RateLimitProperties properties;

    public RateLimitResult tryConsume(RateLimitPolicy policy, UUID userId) {
        ConsumptionProbe probe = proxyManager.builder()
                .build(keyOf(policy, userId), () -> configurationOf(policy))
                .tryConsumeAndReturnRemaining(1);

        if (probe.isConsumed()) {
            return RateLimitResult.allow();
        }
        return RateLimitResult.reject(toRetryAfterSeconds(probe.getNanosToWaitForRefill()));
    }

    private BucketConfiguration configurationOf(RateLimitPolicy policy) {
        Limit limit = properties.limitOf(policy);
        return BucketConfiguration.builder()
                .addLimit(bandwidth -> bandwidth.capacity(limit.capacity())
                        .refillGreedy(limit.capacity(), limit.period()))
                .build();
    }

    private String keyOf(RateLimitPolicy policy, UUID userId) {
        return KEY_PREFIX + policy.name().toLowerCase(Locale.ROOT) + ":" + userId;
    }

    private long toRetryAfterSeconds(long nanosToWait) {
        return Math.max(1, Math.ceilDiv(nanosToWait, TimeUnit.SECONDS.toNanos(1)));
    }
}
