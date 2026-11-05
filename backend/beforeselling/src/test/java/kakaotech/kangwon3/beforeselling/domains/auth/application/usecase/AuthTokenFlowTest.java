package kakaotech.kangwon3.beforeselling.domains.auth.application.usecase;

import com.jayway.jsonpath.JsonPath;
import jakarta.servlet.http.Cookie;
import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.repository.UserRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.cookie.RefreshTokenCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.support.RedisContainerSupport;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 로그인 이후 토큰 흐름(재발급 → 리프레시 토큰 회전 → 로그아웃)을 실제 필터 체인과 Redis로 검증한다.
 */
@Tag("integration")
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AuthTokenFlowTest extends RedisContainerSupport {

    private static final String REISSUE_URL = "/api/v1/auth/reissue";
    private static final String LOGOUT_URL = "/api/v1/auth/logout";
    private static final String AUTHENTICATED_URL = "/api/v1/products";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuthTokenService authTokenService;

    @Autowired
    private UserRepository userRepository;

    private TokenPair loginTokens;

    @BeforeEach
    void setUp() {
        User user = userRepository.save(User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "사용자"));
        loginTokens = authTokenService.issueTokens(user.getId(), Role.USER);
    }

    @AfterEach
    void tearDown() {
        userRepository.deleteAll();
    }

    @Test
    @DisplayName("리프레시 토큰으로 재발급하면 새 액세스 토큰과 회전된 리프레시 토큰 쿠키를 받고, 새 액세스 토큰으로 인증 API를 호출할 수 있다.")
    void reissue_thenNewTokensWork() throws Exception {
        // when
        MvcResult result = mockMvc.perform(post(REISSUE_URL).cookie(refreshCookie(loginTokens.refreshToken())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.accessToken").isNotEmpty())
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString(RefreshTokenCookieProvider.COOKIE_NAME + "=")))
                .andReturn();

        // then
        String newAccessToken = JsonPath.read(result.getResponse().getContentAsString(), "$.data.accessToken");
        mockMvc.perform(get(AUTHENTICATED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + newAccessToken))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("재발급에 한 번 쓴 리프레시 토큰은 다시 쓸 수 없다.")
    void reissue_withUsedRefreshToken_thenUnauthorized() throws Exception {
        // given
        mockMvc.perform(post(REISSUE_URL).cookie(refreshCookie(loginTokens.refreshToken())))
                .andExpect(status().isOk());

        // when & then
        mockMvc.perform(post(REISSUE_URL).cookie(refreshCookie(loginTokens.refreshToken())))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(AuthResponseCode.INVALID_REFRESH_TOKEN.getCode()));
    }

    @Test
    @DisplayName("로그아웃하면 리프레시 토큰 쿠키가 만료되고, 그 리프레시 토큰으로 재발급할 수 없다.")
    void logout_thenRefreshTokenRevoked() throws Exception {
        // when
        mockMvc.perform(post(LOGOUT_URL)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + loginTokens.accessToken())
                        .cookie(refreshCookie(loginTokens.refreshToken())))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.SET_COOKIE, containsString("Max-Age=0")));

        // then
        mockMvc.perform(post(REISSUE_URL).cookie(refreshCookie(loginTokens.refreshToken())))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(AuthResponseCode.INVALID_REFRESH_TOKEN.getCode()));
    }

    @Test
    @DisplayName("변조된 액세스 토큰으로 인증 API를 호출하면 401과 INVALID_ACCESS_TOKEN 코드를 응답한다.")
    void authenticatedApi_withTamperedAccessToken_thenUnauthorized() throws Exception {
        // given
        String tamperedAccessToken = tamperSignature(loginTokens.accessToken());

        // when & then
        mockMvc.perform(get(AUTHENTICATED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + tamperedAccessToken))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(AuthResponseCode.INVALID_ACCESS_TOKEN.getCode()));
    }

    @Test
    @DisplayName("Bearer 형식이 아닌 Authorization 헤더는 토큰으로 보지 않아 401과 COMMON-004 코드를 응답한다.")
    void authenticatedApi_withNonBearerHeader_thenUnauthorized() throws Exception {
        // when & then
        mockMvc.perform(get(AUTHENTICATED_URL).header(HttpHeaders.AUTHORIZATION, "Basic " + loginTokens.accessToken()))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(CommonResponseCode.UNAUTHORIZED.getCode()));
    }

    // 서명 가운데 한 글자를 바꾼다. 끝에 글자를 덧붙이면 Base64URL 디코딩에서 버려져 서명이 그대로 유지되므로 쓰지 않는다.
    private String tamperSignature(String token) {
        int index = token.lastIndexOf('.') + 10;
        char replaced = token.charAt(index) == 'A' ? 'B' : 'A';
        return token.substring(0, index) + replaced + token.substring(index + 1);
    }

    private Cookie refreshCookie(String refreshToken) {
        return new Cookie(RefreshTokenCookieProvider.COOKIE_NAME, refreshToken);
    }
}
