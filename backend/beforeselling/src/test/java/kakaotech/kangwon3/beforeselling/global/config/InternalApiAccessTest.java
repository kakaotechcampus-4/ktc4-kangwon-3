package kakaotech.kangwon3.beforeselling.global.config;

import kakaotech.kangwon3.beforeselling.global.security.filter.InternalTokenFilter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class InternalApiAccessTest {

    private static final String INTERNAL_URI = "/internal/v1/ai/products/01990000-0000-7000-8000-000000000000/events";

    @Autowired
    private MockMvc mockMvc;

    @Value("${internal-api.token}")
    private String internalToken;

    @Test
    @DisplayName("내부 토큰 없이 내부 API를 호출하면 401을 응답한다.")
    void internalApi_withoutToken_thenUnauthorized() throws Exception {
        mockMvc.perform(post(INTERNAL_URI))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("틀린 내부 토큰으로 호출하면 401을 응답한다.")
    void internalApi_withWrongToken_thenUnauthorized() throws Exception {
        mockMvc.perform(post(INTERNAL_URI).header(InternalTokenFilter.HEADER_NAME, internalToken + "x"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("사용자 Bearer 토큰으로는 내부 API를 호출할 수 없다.")
    void internalApi_withBearerToken_thenUnauthorized() throws Exception {
        // 내부 체인에는 JWT 필터가 없으므로 사용자 토큰은 인증으로 인정되지 않는다.
        mockMvc.perform(post(INTERNAL_URI).header(HttpHeaders.AUTHORIZATION, "Bearer any-access-token"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("올바른 내부 토큰이면 보안 체인을 통과한다.")
    void internalApi_withValidToken_thenPassSecurity() throws Exception {
        // 콜백 컨트롤러가 붙기 전이라 404. 401이 아니면 인증 통과다.
        mockMvc.perform(post(INTERNAL_URI).header(InternalTokenFilter.HEADER_NAME, internalToken))
                .andExpect(status().isNotFound());
    }
}
