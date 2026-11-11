package kakaotech.kangwon3.beforeselling.domains.auth.domain.service;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.repository.WithdrawnUserRepository;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.RedisConnectionFailureException;

import java.time.Duration;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class WithdrawnUserServiceTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private WithdrawnUserRepository withdrawnUserRepository;

    @Mock
    private JwtProvider jwtProvider;

    @InjectMocks
    private WithdrawnUserService withdrawnUserService;

    @Test
    @DisplayName("탈퇴 회원을 저장하면 액세스 토큰 만료 시간을 TTL로 저장소에 위임한다.")
    void saveWithdrawnUser_thenDelegateWithAccessTokenExpiration() {
        // given
        Duration accessTokenExpiration = Duration.ofMinutes(30);
        given(jwtProvider.getAccessTokenExpiration()).willReturn(accessTokenExpiration);

        // when
        withdrawnUserService.saveWithdrawnUser(USER_ID);

        // then
        then(withdrawnUserRepository).should().insertWithdrawnUser(USER_ID, accessTokenExpiration);
    }

    @Test
    @DisplayName("블랙리스트에 있는 회원이면 탈퇴 회원으로 판단한다.")
    void isWithdrawn_withSavedUser_thenTrue() {
        // given
        given(withdrawnUserRepository.existsByUserId(USER_ID)).willReturn(true);

        // when & then
        assertThat(withdrawnUserService.isWithdrawn(USER_ID)).isTrue();
    }

    @Test
    @DisplayName("블랙리스트에 없는 회원이면 탈퇴 회원이 아니라고 판단한다.")
    void isWithdrawn_withUnsavedUser_thenFalse() {
        // given
        given(withdrawnUserRepository.existsByUserId(USER_ID)).willReturn(false);

        // when & then
        assertThat(withdrawnUserService.isWithdrawn(USER_ID)).isFalse();
    }

    @Test
    @DisplayName("Redis 조회에 실패하면 요청을 막지 않도록 탈퇴 회원이 아니라고 판단한다.")
    void isWithdrawn_whenRedisFails_thenFalse() {
        // given
        given(withdrawnUserRepository.existsByUserId(USER_ID))
                .willThrow(new RedisConnectionFailureException("connection refused"));

        // when & then
        assertThat(withdrawnUserService.isWithdrawn(USER_ID)).isFalse();
    }
}
