package kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase.LawAmendmentCallbackUseCase;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.ValidationConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.InternalApiProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.filter.InternalTokenFilter;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@Tag("integration")
@WebMvcTest(LawAmendmentCallbackController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, ValidationConfig.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class, InternalApiProperties.class})
class LawAmendmentCallbackControllerTest {

    private static final String URL = "/internal/v1/ai/law-changes";
    private static final String LAW_CHANGES_JSON = """
            {
              "checkedOn": "2026-11-06",
              "changes": [
                {
                  "lawName": "어린이제품 안전 특별법 시행규칙",
                  "documentId": "012345",
                  "admrul": false,
                  "toolName": "CHILDREN",
                  "serialNumber": "291321",
                  "previousSerialNumber": "280000",
                  "revisionType": "일부개정",
                  "enforceDate": "2026-10-20",
                  "issuedDate": "2026-04-20"
                }
              ]
            }
            """;

    @Value("${internal-api.token}")
    private String internalToken;

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private LawAmendmentCallbackUseCase lawAmendmentCallbackUseCase;

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
    @DisplayName("내부 토큰 없이 법령 변경을 보내면 401과 COMMON-004 코드를 응답하고 반영하지 않는다.")
    void receiveLawChanges_withoutToken_thenUnauthorized() throws Exception {
        // when
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(LAW_CHANGES_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));

        // then
        then(lawAmendmentCallbackUseCase).should(never()).receiveLawChanges(any());
    }

    @Test
    @DisplayName("법령 변경을 받으면 반영을 요청하고 200을 응답한다.")
    void receiveLawChanges_thenReceive() throws Exception {
        // when
        mockMvc.perform(callback(LAW_CHANGES_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        // then
        ArgumentCaptor<LawChangeCallbackRequest> captor = ArgumentCaptor.forClass(LawChangeCallbackRequest.class);
        then(lawAmendmentCallbackUseCase).should().receiveLawChanges(captor.capture());

        LawChangeCallbackRequest request = captor.getValue();
        assertThat(request.checkedOn()).isEqualTo(LocalDate.of(2026, 11, 6));
        PublicLawChangeDto change = request.changes().getFirst();
        assertThat(change.toolName()).isEqualTo(ToolName.CHILDREN);
        assertThat(change.admrul()).isFalse();
        assertThat(change.serialNumber()).isEqualTo("291321");
        assertThat(change.enforceDate()).isEqualTo(LocalDate.of(2026, 10, 20));
    }

    @Test
    @DisplayName("변경 목록이 비어 있으면 400과 COMMON-002 코드를 응답하고 반영하지 않는다.")
    void receiveLawChanges_withEmptyChanges_thenInvalid() throws Exception {
        // when
        mockMvc.perform(callback("""
                        {"checkedOn": "2026-11-06", "changes": []}"""))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));

        // then
        then(lawAmendmentCallbackUseCase).should(never()).receiveLawChanges(any());
    }

    @Test
    @DisplayName("변경의 판 번호가 비어 있으면 400과 COMMON-002 코드를 응답하고 반영하지 않는다.")
    void receiveLawChanges_withBlankSerialNumber_thenInvalid() throws Exception {
        // when
        mockMvc.perform(callback(LAW_CHANGES_JSON.replace("\"291321\"", "\" \"")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));

        // then
        then(lawAmendmentCallbackUseCase).should(never()).receiveLawChanges(any());
    }

    @Test
    @DisplayName("알 수 없는 분야를 보내면 400과 COMMON-001 코드를 응답하고 반영하지 않는다.")
    void receiveLawChanges_withUnknownToolName_thenBadRequest() throws Exception {
        // when
        mockMvc.perform(callback(LAW_CHANGES_JSON.replace("\"CHILDREN\"", "\"RADIATION\"")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-001"));

        // then
        then(lawAmendmentCallbackUseCase).should(never()).receiveLawChanges(any());
    }

    private MockHttpServletRequestBuilder callback(String json) {
        return post(URL)
                .header(InternalTokenFilter.HEADER_NAME, internalToken)
                .contentType(MediaType.APPLICATION_JSON)
                .content(json);
    }
}
