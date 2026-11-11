package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.repository.UserRepository;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenPair;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink.SocialUnlinkService;
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
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 회원 탈퇴 이후 남아 있는 액세스 토큰이 실제 필터 체인과 Redis에서 거절되는지 검증한다.
 */
@Tag("integration")
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class UserWithdrawalFlowTest extends RedisContainerSupport {

    private static final String WITHDRAW_URL = "/api/v1/users/me";
    private static final String AUTHENTICATED_URL = "/api/v1/products";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private AuthTokenService authTokenService;

    @Autowired
    private UserRepository userRepository;

    @MockitoBean
    private SocialUnlinkService socialUnlinkService;

    private String accessToken;

    @BeforeEach
    void setUp() {
        User user = userRepository.save(User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "사용자"));
        TokenPair tokens = authTokenService.issueTokens(user.getId(), Role.USER);
        accessToken = tokens.accessToken();
    }

    @AfterEach
    void tearDown() {
        userRepository.deleteAll();
    }

    @Test
    @DisplayName("탈퇴한 뒤 만료 전인 액세스 토큰으로 인증 API를 호출하면 401과 INVALID_ACCESS_TOKEN 코드를 응답한다.")
    void authenticatedApi_afterWithdrawal_thenUnauthorized() throws Exception {
        // given
        mockMvc.perform(delete(WITHDRAW_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
                .andExpect(status().isNoContent());

        // when & then
        mockMvc.perform(get(AUTHENTICATED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(AuthResponseCode.INVALID_ACCESS_TOKEN.getCode()));
    }
}
