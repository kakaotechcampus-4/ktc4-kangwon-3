package kakaotech.kangwon3.beforeselling.domains.user.presentation.controller;

import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.domains.user.application.usecase.UserWithdrawalUseCase;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
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
import static org.mockito.BDDMockito.then;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, RefreshTokenCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class})
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private UserWithdrawalUseCase userWithdrawalUseCase;

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
    @DisplayName("인증 없이 회원 탈퇴를 요청하면 401과 COMMON-004 코드를 응답한다.")
    void withdraw_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(delete("/api/v1/users/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("인증된 회원이 탈퇴를 요청하면 성공하고 리프레시 토큰 쿠키가 만료된다.")
    void withdraw_thenSuccessAndExpireCookie() throws Exception {
        // given
        Authentication authentication = UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(1L, Role.USER), null, List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));

        // when & then
        mockMvc.perform(delete("/api/v1/users/me")
                        .with(authentication(authentication))
                        .cookie(new Cookie(RefreshTokenCookieProvider.COOKIE_NAME, "refresh")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("refresh_token=;")))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("Max-Age=0")));
        then(userWithdrawalUseCase).should().withdraw(1L, "refresh");
    }
}
