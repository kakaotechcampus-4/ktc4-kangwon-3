package kakaotech.kangwon3.beforeselling.global.security.filter;

import jakarta.servlet.FilterChain;
import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.WithdrawnUserService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenClaims;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenType;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class JwtAuthenticationFilterTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String ACCESS_TOKEN = "access-token";

    @Mock
    private JwtProvider jwtProvider;

    @Mock
    private WithdrawnUserService withdrawnUserService;

    @Mock
    private FilterChain filterChain;

    private JwtAuthenticationFilter filter;
    private MockHttpServletRequest request;
    private MockHttpServletResponse response;

    @BeforeEach
    void setUp() {
        filter = new JwtAuthenticationFilter(jwtProvider, withdrawnUserService, req -> false);
        request = new MockHttpServletRequest();
        response = new MockHttpServletResponse();
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    @Test
    @DisplayName("탈퇴한 회원의 액세스 토큰이면 INVALID_ACCESS_TOKEN 예외를 던지고 다음 필터로 넘기지 않는다.")
    void doFilter_withWithdrawnUser_thenThrowAndStopChain() throws Exception {
        // given
        request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer " + ACCESS_TOKEN);
        given(jwtProvider.parse(ACCESS_TOKEN, TokenType.ACCESS)).willReturn(accessClaims());
        given(withdrawnUserService.isWithdrawn(USER_ID)).willReturn(true);

        // when & then
        assertThatThrownBy(() -> filter.doFilter(request, response, filterChain))
                .isInstanceOf(BaseException.class)
                .extracting("responseCode")
                .isEqualTo(AuthResponseCode.INVALID_ACCESS_TOKEN);
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        then(filterChain).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("탈퇴하지 않은 회원의 액세스 토큰이면 인증 정보를 채우고 다음 필터로 넘긴다.")
    void doFilter_withActiveUser_thenAuthenticateAndContinue() throws Exception {
        // given
        request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer " + ACCESS_TOKEN);
        given(jwtProvider.parse(ACCESS_TOKEN, TokenType.ACCESS)).willReturn(accessClaims());
        given(withdrawnUserService.isWithdrawn(USER_ID)).willReturn(false);

        // when
        filter.doFilter(request, response, filterChain);

        // then
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        assertThat(authentication.getPrincipal()).isEqualTo(new UserPrincipal(USER_ID, Role.USER));
        then(filterChain).should().doFilter(request, response);
    }

    @Test
    @DisplayName("액세스 토큰이 없으면 탈퇴 여부를 조회하지 않고 다음 필터로 넘긴다.")
    void doFilter_withoutToken_thenSkipWithdrawnCheck() throws Exception {
        // when
        filter.doFilter(request, response, filterChain);

        // then
        then(withdrawnUserService).should(never()).isWithdrawn(any());
        then(filterChain).should().doFilter(request, response);
    }

    private TokenClaims accessClaims() {
        return new TokenClaims(USER_ID, Role.USER, TokenType.ACCESS, "jti");
    }
}
