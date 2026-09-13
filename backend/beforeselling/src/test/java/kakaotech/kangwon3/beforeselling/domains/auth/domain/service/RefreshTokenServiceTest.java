package kakaotech.kangwon3.beforeselling.domains.auth.domain.service;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.repository.RefreshTokenRepository;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Duration;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class RefreshTokenServiceTest {

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

    @InjectMocks
    private RefreshTokenService refreshTokenService;

    @Test
    @DisplayName("리프레시 토큰을 저장하면 저장소에 jti/userId/TTL이 그대로 위임된다.")
    void saveRefreshToken_thenDelegateToRepository() {
        // given
        Duration ttl = Duration.ofDays(14);

        // when
        refreshTokenService.saveRefreshToken("jti", 1L, ttl);

        // then
        then(refreshTokenRepository).should().insertRefreshToken("jti", 1L, ttl);
    }

    @Test
    @DisplayName("저장된 jti이고 소유자가 일치하면 소비에 성공한다.")
    void consumeRefreshToken_withOwnedJti_thenSucceed() {
        // given
        given(refreshTokenRepository.getAndDeleteUserIdByJti("jti")).willReturn(Optional.of(1L));

        // when & then
        assertThatCode(() -> refreshTokenService.consumeRefreshToken("jti", 1L))
                .doesNotThrowAnyException();
    }

    @Test
    @DisplayName("저장소에 없는(이미 소비되었거나 만료된) jti로 소비를 시도하면 INVALID_REFRESH_TOKEN 예외가 발생한다.")
    void consumeRefreshToken_withUnknownJti_thenThrow() {
        // given
        given(refreshTokenRepository.getAndDeleteUserIdByJti("jti")).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> refreshTokenService.consumeRefreshToken("jti", 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_REFRESH_TOKEN);
    }

    @Test
    @DisplayName("저장된 jti의 소유자와 요청한 userId가 다르면, GETDEL로 이미 소비된 뒤에도 방어적으로 INVALID_REFRESH_TOKEN 예외가 발생한다.")
    void consumeRefreshToken_withMismatchedOwner_thenThrow() {
        // given: jti는 존재하지만 저장된 소유자(2L)와 요청한 userId(1L)가 다른 방어적 시나리오
        given(refreshTokenRepository.getAndDeleteUserIdByJti("jti")).willReturn(Optional.of(2L));

        // when & then
        assertThatThrownBy(() -> refreshTokenService.consumeRefreshToken("jti", 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_REFRESH_TOKEN);
    }

    @Test
    @DisplayName("리프레시 토큰을 제거하면 저장소에서 해당 jti가 삭제된다.")
    void removeRefreshToken_thenDeleteFromRepository() {
        // when
        refreshTokenService.removeRefreshToken("jti");

        // then
        then(refreshTokenRepository).should().deleteRefreshToken("jti");
    }
}
