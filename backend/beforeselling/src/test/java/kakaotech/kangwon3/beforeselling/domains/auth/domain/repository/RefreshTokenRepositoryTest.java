package kakaotech.kangwon3.beforeselling.domains.auth.domain.repository;

import kakaotech.kangwon3.beforeselling.support.RedisContainerSupport;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.redis.test.autoconfigure.DataRedisTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.ActiveProfiles;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("integration")
@DataRedisTest
@ActiveProfiles("test")
@Import(RefreshTokenRepository.class)
class RefreshTokenRepositoryTest extends RedisContainerSupport {

    private static final String JTI = "test-jti";
    private static final String KEY = "refresh_token:" + JTI;

    @Autowired
    private RefreshTokenRepository refreshTokenRepository;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @AfterEach
    void tearDown() {
        redisTemplate.delete(KEY);
    }

    @Test
    @DisplayName("리프레시 토큰을 저장하면 jti 키에 사용자 ID가 만료 시간과 함께 저장된다.")
    void insertRefreshToken_thenSaveUserIdWithTtl() {
        // given
        UUID userId = UUID.randomUUID();

        // when
        refreshTokenRepository.insertRefreshToken(JTI, userId, Duration.ofDays(14));

        // then
        assertThat(redisTemplate.opsForValue().get(KEY)).isEqualTo(userId.toString());
        assertThat(redisTemplate.getExpire(KEY)).isPositive().isLessThanOrEqualTo(Duration.ofDays(14).toSeconds());
    }

    @Test
    @DisplayName("저장된 리프레시 토큰은 한 번만 꺼낼 수 있다.")
    void getAndDeleteUserIdByJti_thenReturnOnlyOnce() {
        // given
        UUID userId = UUID.randomUUID();
        refreshTokenRepository.insertRefreshToken(JTI, userId, Duration.ofDays(14));

        // when
        var first = refreshTokenRepository.getAndDeleteUserIdByJti(JTI);
        var second = refreshTokenRepository.getAndDeleteUserIdByJti(JTI);

        // then
        assertThat(first).contains(userId);
        assertThat(second).isEmpty();
    }

    @Test
    @DisplayName("없는 jti로 꺼내면 빈 값을 돌려준다.")
    void getAndDeleteUserIdByJti_withUnknownJti_thenEmpty() {
        // when & then
        assertThat(refreshTokenRepository.getAndDeleteUserIdByJti("unknown-jti")).isEmpty();
    }

    @Test
    @DisplayName("리프레시 토큰을 삭제하면 다시 꺼낼 수 없다.")
    void deleteRefreshToken_thenCannotGet() {
        // given
        refreshTokenRepository.insertRefreshToken(JTI, UUID.randomUUID(), Duration.ofDays(14));

        // when
        refreshTokenRepository.deleteRefreshToken(JTI);

        // then
        assertThat(refreshTokenRepository.getAndDeleteUserIdByJti(JTI)).isEmpty();
    }
}
