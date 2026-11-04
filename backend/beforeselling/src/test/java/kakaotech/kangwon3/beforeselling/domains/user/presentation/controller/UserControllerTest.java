package kakaotech.kangwon3.beforeselling.domains.user.presentation.controller;

import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.UserProfileModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.UserProfileResponse;
import kakaotech.kangwon3.beforeselling.domains.user.application.usecase.UserProfileUseCase;
import kakaotech.kangwon3.beforeselling.domains.user.application.usecase.UserWithdrawalUseCase;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.InternalApiProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Tag("integration")
@WebMvcTest(UserController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, RefreshTokenCookieProvider.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class, InternalApiProperties.class})
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private UserWithdrawalUseCase userWithdrawalUseCase;

    @MockitoBean
    private UserProfileUseCase userProfileUseCase;

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

    @MockitoBean
    private OAuth2AuthorizedClientRepository authorizedClientRepository;

    @Test
    @DisplayName("인증 없이 회원 탈퇴를 요청하면 401과 COMMON-004 코드를 응답한다.")
    void withdraw_withoutAuthentication_thenUnauthorized() throws Exception {
        // when & then
        mockMvc.perform(delete("/api/v1/users/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("인증된 회원이 탈퇴를 요청하면 본문 없이 204 응답을 받고 리프레시 토큰 쿠키가 만료된다.")
    void withdraw_thenNoContentAndExpireCookie() throws Exception {
        // given
        UUID userId = UUID.randomUUID();
        Authentication authentication = UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(userId, Role.USER), null, List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));

        // when & then
        mockMvc.perform(delete("/api/v1/users/me")
                        .with(authentication(authentication))
                        .cookie(new Cookie(RefreshTokenCookieProvider.COOKIE_NAME, "refresh")))
                .andExpect(status().isNoContent())
                .andExpect(content().string(""))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("refresh_token=;")))
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("Max-Age=0")));
        then(userWithdrawalUseCase).should().withdraw(userId, "refresh");
    }

    @Test
    @DisplayName("인증 없이 내 정보를 조회하면 401과 COMMON-004 코드를 응답한다.")
    void getMyProfile_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(get("/api/v1/users/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("내 정보를 조회하면 이름, 이메일, 소셜 제공자를 응답한다.")
    void getMyProfile_thenReturnProfile() throws Exception {
        // given
        UUID userId = UUID.randomUUID();
        given(userProfileUseCase.getMyProfile(userId))
                .willReturn(new UserProfileResponse("사용자", "user@example.com", SocialProvider.KAKAO));

        // when & then
        mockMvc.perform(get("/api/v1/users/me")
                        .with(authentication(loginUser(userId))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.name").value("사용자"))
                .andExpect(jsonPath("$.data.email").value("user@example.com"))
                .andExpect(jsonPath("$.data.socialProvider").value("KAKAO"));
    }

    @Test
    @DisplayName("이름을 수정하면 수정된 내 정보를 응답한다.")
    void modifyMyProfile_thenReturnModifiedProfile() throws Exception {
        // given
        UUID userId = UUID.randomUUID();
        given(userProfileUseCase.modifyMyProfile(userId, new UserProfileModifyRequest("새 이름")))
                .willReturn(new UserProfileResponse("새 이름", "user@example.com", SocialProvider.KAKAO));

        // when & then
        mockMvc.perform(patch("/api/v1/users/me")
                        .with(authentication(loginUser(userId)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name": "새 이름"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.name").value("새 이름"));
    }

    @Test
    @DisplayName("공백만 있는 이름으로는 수정할 수 없고 400과 COMMON-002 코드를 응답한다.")
    void modifyMyProfile_withBlankName_thenBadRequest() throws Exception {
        mockMvc.perform(patch("/api/v1/users/me")
                        .with(authentication(loginUser(UUID.randomUUID())))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name": "   "}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
        then(userProfileUseCase).should(never()).modifyMyProfile(any(), any());
    }

    @Test
    @DisplayName("이름이 20자를 넘으면 수정할 수 없고 400과 COMMON-002 코드를 응답한다.")
    void modifyMyProfile_withTooLongName_thenBadRequest() throws Exception {
        mockMvc.perform(patch("/api/v1/users/me")
                        .with(authentication(loginUser(UUID.randomUUID())))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\": \"%s\"}".formatted("가".repeat(21))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("이름이 정확히 20자이면 수정할 수 있다.")
    void modifyMyProfile_withNameOf20Chars_thenOk() throws Exception {
        UUID userId = UUID.randomUUID();
        String name = "가".repeat(20);
        given(userProfileUseCase.modifyMyProfile(userId, new UserProfileModifyRequest(name)))
                .willReturn(new UserProfileResponse(name, "user@example.com", SocialProvider.KAKAO));

        mockMvc.perform(patch("/api/v1/users/me")
                        .with(authentication(loginUser(userId)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\": \"%s\"}".formatted(name)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.name").value(name));
    }

    private Authentication loginUser(UUID userId) {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(userId, Role.USER), null, List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }
}
