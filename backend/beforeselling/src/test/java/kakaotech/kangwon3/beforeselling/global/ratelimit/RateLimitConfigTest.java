package kakaotech.kangwon3.beforeselling.global.ratelimit;

import io.github.bucket4j.TimeoutException;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.api.async.RedisAsyncCommands;
import io.lettuce.core.protocol.AsyncCommand;
import io.lettuce.core.protocol.Command;
import io.lettuce.core.protocol.CommandType;
import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties.Limit;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

class RateLimitConfigTest {

    private final RateLimitProperties properties = new RateLimitProperties(
            new Limit(3, Duration.ofMinutes(1)),
            new Limit(2, Duration.ofMinutes(1))
    );

    @Test
    @DisplayName("Redis가 응답하지 않으면 command timeout까지 기다리지 않고 100ms 안팎에서 한도 확인을 포기한다")
    @SuppressWarnings("unchecked")
    void givesUpQuicklyWhenRedisDoesNotRespond() {
        // given
        StatefulRedisConnection<String, byte[]> connection = mock(StatefulRedisConnection.class);
        RedisAsyncCommands<String, byte[]> commands = mock(RedisAsyncCommands.class);
        given(connection.async()).willReturn(commands);
        // 끊긴 연결에서 재연결을 기다리며 큐에 쌓인 명령처럼, 완료되지 않는 응답
        given(commands.get(anyString())).willAnswer(invocation -> new AsyncCommand<>(new Command<>(CommandType.GET, null)));
        RateLimiter rateLimiter = new RateLimiter(new RateLimitConfig().rateLimitProxyManager(connection), properties);

        // when & then
        assertTimeoutPreemptively(Duration.ofSeconds(1), () ->
                assertThatThrownBy(() -> rateLimiter.tryConsume(RateLimitPolicy.DEFAULT, UUID.randomUUID()))
                        .isInstanceOf(TimeoutException.class)
        );
    }
}
