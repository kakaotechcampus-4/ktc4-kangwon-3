package kakaotech.kangwon3.beforeselling.domains.auth.presentation.controller;

import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.domains.auth.application.usecase.AuthUseCase;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenType;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AuthController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, RefreshTokenCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class})
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AuthUseCase authUseCase;

    @MockitoBean
    private JwtProvider jwtProvider;

    @MockitoBean
    private CustomOAuth2UserService customOAuth2UserService;

    @MockitoBean
    private OAuth2SuccessHandler oAuth2SuccessHandler;

    @MockitoBean
    private OAuth2FailureHandler oAuth2FailureHandler;

    @MockitoBean
    private RedisOAuth2AuthorizationRequestRepository authorizationRequestRepository;

    @Test
    @DisplayName("리프레시 토큰 쿠키 없이 재발급을 요청하면 401과 AUTH-003 코드를 응답한다.")
    void reissue_withoutCookie_thenUnauthorized() throws Exception {
        // given
        given(authUseCase.reissueToken(null))
                .willThrow(new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN));

        // when & then
        mockMvc.perform(post("/api/v1/auth/reissue"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH-003"));
    }

    @Test
    @DisplayName("리프레시 토큰 쿠키로 재발급하면 액세스 토큰과 새 리프레시 토큰 쿠키를 응답한다.")
    void reissue_withCookie_thenReturnAccessTokenAndRotateCookie() throws Exception {
        // given
        given(authUseCase.reissueToken("old-refresh"))
                .willReturn(new TokenPair("new-access", "new-refresh", "new-jti", 1800L));

        // when & then
        mockMvc.perform(post("/api/v1/auth/reissue")
                        .cookie(new Cookie(RefreshTokenCookieProvider.COOKIE_NAME, "old-refresh")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.accessToken").value("new-access"))
                .andExpect(jsonPath("$.data.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.data.expiresIn").value(1800))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("refresh_token=new-refresh")))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("HttpOnly")))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("Path=/api/v1/auth")))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("SameSite=Lax")));
    }

    @Test
    @DisplayName("인증 없이 로그아웃을 요청하면 401과 COMMON-004 코드를 응답한다.")
    void logout_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(post("/api/v1/auth/logout"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("만료된 액세스 토큰으로 요청하면 401과 AUTH-001 코드를 응답한다.")
    void request_withExpiredAccessToken_thenUnauthorized() throws Exception {
        // given
        given(jwtProvider.parse("expired-token", TokenType.ACCESS))
                .willThrow(new BaseException(AuthResponseCode.EXPIRED_ACCESS_TOKEN));

        // when & then
        mockMvc.perform(post("/api/v1/auth/logout")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer expired-token"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH-001"));
    }

    @Test
    @DisplayName("로그아웃하면 리프레시 토큰이 폐기되고 쿠키가 만료된다.")
    void logout_thenExpireCookie() throws Exception {
        // given
        Authentication authentication = UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(1L, Role.USER), null, List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));

        // when & then
        mockMvc.perform(post("/api/v1/auth/logout")
                        .with(authentication(authentication))
                        .cookie(new Cookie(RefreshTokenCookieProvider.COOKIE_NAME, "refresh")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("refresh_token=;")))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("Max-Age=0")));
        then(authUseCase).should().logout("refresh");
    }
}
