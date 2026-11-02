package kakaotech.kangwon3.beforeselling.global.config.properties;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import kakaotech.kangwon3.beforeselling.global.ratelimit.RateLimitPolicy;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

@Validated
@ConfigurationProperties(prefix = "rate-limit")
public record RateLimitProperties(
        @NotNull @Valid Limit defaultPolicy,
        @NotNull @Valid Limit ai
) {

    public Limit limitOf(RateLimitPolicy policy) {
        return switch (policy) {
            case DEFAULT -> defaultPolicy;
            case AI -> ai;
        };
    }

    // period 동안 capacity번까지 허용
    public record Limit(
            @Positive long capacity,
            @NotNull Duration period
    ) {
    }
}
