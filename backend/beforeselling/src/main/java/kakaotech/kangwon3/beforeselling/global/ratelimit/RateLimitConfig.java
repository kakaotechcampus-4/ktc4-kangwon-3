package kakaotech.kangwon3.beforeselling.global.ratelimit;

import io.github.bucket4j.distributed.ExpirationAfterWriteStrategy;
import io.github.bucket4j.distributed.proxy.ProxyManager;
import io.github.bucket4j.redis.lettuce.Bucket4jLettuce;
import io.lettuce.core.RedisClient;
import io.lettuce.core.api.StatefulRedisConnection;
import io.lettuce.core.codec.ByteArrayCodec;
import io.lettuce.core.codec.RedisCodec;
import io.lettuce.core.codec.StringCodec;
import kakaotech.kangwon3.beforeselling.global.config.properties.RateLimitProperties;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.time.Duration;

@Configuration
public class RateLimitConfig {

    @Lazy
    @Bean(destroyMethod = "close")
    public StatefulRedisConnection<String, byte[]> rateLimitRedisConnection(LettuceConnectionFactory connectionFactory) {
        RedisClient redisClient = (RedisClient) connectionFactory.getNativeClient();
        return redisClient.connect(RedisCodec.of(StringCodec.UTF8, ByteArrayCodec.INSTANCE));
    }

    @Lazy
    @Bean
    public ProxyManager<String> rateLimitProxyManager(StatefulRedisConnection<String, byte[]> rateLimitRedisConnection) {
        return Bucket4jLettuce.casBasedBuilder(rateLimitRedisConnection)
                .expirationAfterWrite(ExpirationAfterWriteStrategy.basedOnTimeForRefillingBucketUpToMax(Duration.ofSeconds(10)))
                .build();
    }

    @Bean
    public RateLimiter rateLimiter(@Lazy ProxyManager<String> rateLimitProxyManager, RateLimitProperties properties) {
        return new RateLimiter(rateLimitProxyManager, properties);
    }

    @Bean
    public WebMvcConfigurer rateLimitWebMvcConfigurer(RateLimiter rateLimiter, ApiResponseWriter apiResponseWriter) {
        RateLimitInterceptor interceptor = new RateLimitInterceptor(rateLimiter, apiResponseWriter);
        return new WebMvcConfigurer() {
            @Override
            public void addInterceptors(InterceptorRegistry registry) {
                registry.addInterceptor(interceptor).addPathPatterns("/api/**");
            }
        };
    }
}
