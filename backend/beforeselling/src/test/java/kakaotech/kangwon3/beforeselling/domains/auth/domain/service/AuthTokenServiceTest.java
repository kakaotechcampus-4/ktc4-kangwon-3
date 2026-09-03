package kakaotech.kangwon3.beforeselling.domains.auth.domain.service;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenClaims;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenType;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.inOrder;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class AuthTokenServiceTest {

    private static final Duration REFRESH_TTL = Duration.ofDays(14);

    @Mock
    private JwtProvider jwtProvider;

    @Mock
    private RefreshTokenService refreshTokenService;

    @Mock
    private UserService userService;

    @InjectMocks
    private AuthTokenService authTokenService;

    @Test
    @DisplayName("토큰을 발급하면 리프레시 토큰의 jti가 만료 시간과 함께 저장된다.")
    void issueTokens_thenSaveRefreshTokenJti() {
        // given
        TokenPair tokenPair = new TokenPair("access", "refresh", "new-jti", 1800L);
        given(jwtProvider.issueTokenPair(1L, Role.USER)).willReturn(tokenPair);
        given(jwtProvider.getRefreshTokenExpiration()).willReturn(REFRESH_TTL);

        // when
        TokenPair result = authTokenService.issueTokens(1L, Role.USER);

        // then
        assertThat(result).isEqualTo(tokenPair);
        then(refreshTokenService).should().saveRefreshToken("new-jti", 1L, REFRESH_TTL);
    }

    @Test
    @DisplayName("유효한 리프레시 토큰으로 재발급하면 기존 토큰은 삭제되고 새 토큰 쌍이 발급된다.")
    void reissueTokens_thenRotateRefreshToken() {
        // given
        User user = createUser(1L, Role.USER);
        TokenPair newPair = new TokenPair("new-access", "new-refresh", "new-jti", 1800L);
        given(jwtProvider.parse("old-refresh", TokenType.REFRESH))
                .willReturn(new TokenClaims(1L, Role.USER, TokenType.REFRESH, "old-jti"));
        given(userService.getUser(1L)).willReturn(user);
        given(jwtProvider.issueTokenPair(1L, Role.USER)).willReturn(newPair);
        given(jwtProvider.getRefreshTokenExpiration()).willReturn(REFRESH_TTL);

        // when
        TokenPair result = authTokenService.reissueTokens("old-refresh");

        // then
        assertThat(result).isEqualTo(newPair);
        InOrder inOrder = inOrder(refreshTokenService);
        then(refreshTokenService).should(inOrder).validateRefreshToken("old-jti", 1L);
        then(refreshTokenService).should(inOrder).removeRefreshToken("old-jti");
        then(refreshTokenService).should(inOrder).saveRefreshToken("new-jti", 1L, REFRESH_TTL);
    }

    @Test
    @DisplayName("저장소에 존재하지 않는 리프레시 토큰으로 재발급하면 INVALID_REFRESH_TOKEN 예외가 발생하고 새 토큰은 발급되지 않는다.")
    void reissueTokens_withUnknownJti_thenThrow() {
        // given
        given(jwtProvider.parse("old-refresh", TokenType.REFRESH))
                .willReturn(new TokenClaims(1L, Role.USER, TokenType.REFRESH, "old-jti"));
        willThrow(new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN))
                .given(refreshTokenService).validateRefreshToken("old-jti", 1L);

        // when & then
        assertThatThrownBy(() -> authTokenService.reissueTokens("old-refresh"))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.INVALID_REFRESH_TOKEN);
        then(jwtProvider).should(never()).issueTokenPair(any(), any());
        then(refreshTokenService).should(never()).removeRefreshToken(anyString());
    }

    @Test
    @DisplayName("재발급 시 사용자의 역할은 DB 기준으로 최신화된다.")
    void reissueTokens_thenUseLatestRole() {
        // given
        User admin = createUser(1L, Role.ADMIN);
        given(jwtProvider.parse("old-refresh", TokenType.REFRESH))
                .willReturn(new TokenClaims(1L, Role.USER, TokenType.REFRESH, "old-jti"));
        given(userService.getUser(1L)).willReturn(admin);
        given(jwtProvider.issueTokenPair(1L, Role.ADMIN))
                .willReturn(new TokenPair("a", "r", "new-jti", 1800L));
        given(jwtProvider.getRefreshTokenExpiration()).willReturn(REFRESH_TTL);

        // when
        authTokenService.reissueTokens("old-refresh");

        // then
        then(jwtProvider).should().issueTokenPair(1L, Role.ADMIN);
    }

    @Test
    @DisplayName("로그아웃하면 리프레시 토큰이 저장소에서 삭제된다.")
    void removeRefreshToken_thenDelete() {
        // given
        given(jwtProvider.parse("refresh", TokenType.REFRESH))
                .willReturn(new TokenClaims(1L, Role.USER, TokenType.REFRESH, "jti"));

        // when
        authTokenService.removeRefreshToken("refresh");

        // then
        then(refreshTokenService).should().removeRefreshToken("jti");
    }

    @Test
    @DisplayName("유효하지 않은 리프레시 토큰으로 로그아웃해도 예외 없이 처리된다.")
    void removeRefreshToken_withInvalidToken_thenIgnore() {
        // given
        given(jwtProvider.parse("broken", TokenType.REFRESH))
                .willThrow(new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN));

        // when
        authTokenService.removeRefreshToken("broken");

        // then
        then(refreshTokenService).should(never()).removeRefreshToken(anyString());
    }

    @Test
    @DisplayName("리프레시 토큰 쿠키가 없는 상태로 로그아웃하면 저장소 접근 없이 처리된다.")
    void removeRefreshToken_withNull_thenNoop() {
        // when
        authTokenService.removeRefreshToken(null);

        // then
        then(jwtProvider).shouldHaveNoInteractions();
        then(refreshTokenService).shouldHaveNoInteractions();
    }

    private User createUser(Long id, Role role) {
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "id", id);
        ReflectionTestUtils.setField(user, "role", role);
        return user;
    }
}
