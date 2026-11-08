package kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase.LawAmendmentUseCase;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.InternalApiProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
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
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Tag("integration")
@WebMvcTest(LawAmendmentController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class, InternalApiProperties.class})
class LawAmendmentControllerTest {

    private static final String URL = "/api/v1/law-amendments";
    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID LAW_AMENDMENT_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final UUID DIAGNOSES_ID = UUID.randomUUID();

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private LawAmendmentUseCase lawAmendmentUseCase;

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
    @DisplayName("인증 없이 재확인 대상 상품을 조회하면 401과 COMMON-004 코드를 응답한다.")
    void getLawAmendments_withoutAuthentication_thenUnauthorized() throws Exception {
        // when
        mockMvc.perform(get(URL))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));

        // then
        then(lawAmendmentUseCase).should(never()).getLawAmendments(any());
    }

    @Test
    @DisplayName("재확인 대상 상품을 조회하면 개정별로 묶어 응답한다.")
    void getLawAmendments_thenReturnLawAmendments() throws Exception {
        // given
        given(lawAmendmentUseCase.getLawAmendments(USER_ID)).willReturn(new LawAmendmentListResponse(List.of(
                new LawAmendmentResponse(LAW_AMENDMENT_ID, "어린이제품 안전 특별법 시행규칙", "일부개정",
                        ToolName.CHILDREN, LocalDate.of(2026, 10, 20),
                        List.of(new LawAmendmentResponse.RecheckProductResponse(PRODUCT_ID, DIAGNOSES_ID, "대나무 헬리콥터"))))));

        // when & then
        mockMvc.perform(get(URL).with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.lawAmendments[0].lawAmendmentId").value(LAW_AMENDMENT_ID.toString()))
                .andExpect(jsonPath("$.data.lawAmendments[0].lawName").value("어린이제품 안전 특별법 시행규칙"))
                .andExpect(jsonPath("$.data.lawAmendments[0].revisionType").value("일부개정"))
                .andExpect(jsonPath("$.data.lawAmendments[0].toolName").value("CHILDREN"))
                .andExpect(jsonPath("$.data.lawAmendments[0].enforceDate").value("2026-10-20"))
                .andExpect(jsonPath("$.data.lawAmendments[0].products[0].productId").value(PRODUCT_ID.toString()))
                .andExpect(jsonPath("$.data.lawAmendments[0].products[0].diagnosesId").value(DIAGNOSES_ID.toString()))
                .andExpect(jsonPath("$.data.lawAmendments[0].products[0].productName").value("대나무 헬리콥터"));
    }

    private Authentication loginUser() {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(USER_ID, Role.USER),
                null,
                List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }
}
