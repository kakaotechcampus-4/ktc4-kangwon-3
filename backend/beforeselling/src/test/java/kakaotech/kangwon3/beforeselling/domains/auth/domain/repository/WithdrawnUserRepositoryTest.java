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
@Import(WithdrawnUserRepository.class)
class WithdrawnUserRepositoryTest extends RedisContainerSupport {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String KEY = "withdrawn_user:" + USER_ID;

    @Autowired
    private WithdrawnUserRepository withdrawnUserRepository;

    @Autowired
    private StringRedisTemplate redisTemplate;

    @AfterEach
    void tearDown() {
        redisTemplate.delete(KEY);
    }

    @Test
    @DisplayName("탈퇴 회원을 저장하면 userId 키가 만료 시간과 함께 저장된다.")
    void insertWithdrawnUser_thenSaveKeyWithTtl() {
        // when
        withdrawnUserRepository.insertWithdrawnUser(USER_ID, Duration.ofMinutes(30));

        // then
        assertThat(redisTemplate.hasKey(KEY)).isTrue();
        assertThat(redisTemplate.getExpire(KEY)).isPositive().isLessThanOrEqualTo(Duration.ofMinutes(30).toSeconds());
    }

    @Test
    @DisplayName("저장된 탈퇴 회원은 존재한다고 조회된다.")
    void existsByUserId_withSavedUser_thenTrue() {
        // given
        withdrawnUserRepository.insertWithdrawnUser(USER_ID, Duration.ofMinutes(30));

        // when & then
        assertThat(withdrawnUserRepository.existsByUserId(USER_ID)).isTrue();
    }

    @Test
    @DisplayName("저장되지 않은 회원은 존재하지 않는다고 조회된다.")
    void existsByUserId_withUnsavedUser_thenFalse() {
        // when & then
        assertThat(withdrawnUserRepository.existsByUserId(UUID.randomUUID())).isFalse();
    }
}
