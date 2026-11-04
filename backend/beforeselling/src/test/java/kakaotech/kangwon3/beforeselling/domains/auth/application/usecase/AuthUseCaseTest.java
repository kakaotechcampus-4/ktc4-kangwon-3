package kakaotech.kangwon3.beforeselling.domains.auth.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class AuthUseCaseTest {

    @Mock
    private AuthTokenService authTokenService;

    @InjectMocks
    private AuthUseCase authUseCase;

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   "})
    @DisplayName("리프레시 토큰이 없거나 비어 있으면 재발급하지 않고 INVALID_REFRESH_TOKEN 예외가 발생한다.")
    void reissueToken_withoutRefreshToken_thenThrow(String refreshToken) {
        // when & then
        assertThatThrownBy(() -> authUseCase.reissueToken(refreshToken))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_REFRESH_TOKEN);
        then(authTokenService).should(never()).reissueTokens(any());
    }

    @Test
    @DisplayName("리프레시 토큰이 있으면 새 토큰 쌍을 발급한다.")
    void reissueToken_withRefreshToken_thenReturnNewTokenPair() {
        // given
        TokenPair tokenPair = new TokenPair("new-access", "new-refresh", "new-jti", 1800);
        given(authTokenService.reissueTokens("refresh-token")).willReturn(tokenPair);

        // when
        TokenPair result = authUseCase.reissueToken("refresh-token");

        // then
        assertThat(result).isEqualTo(tokenPair);
    }

    @Test
    @DisplayName("로그아웃하면 리프레시 토큰을 폐기한다.")
    void logout_thenRemoveRefreshToken() {
        // when
        authUseCase.logout("refresh-token");

        // then
        then(authTokenService).should().removeRefreshToken("refresh-token");
    }
}
