package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductAwaitingInputEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductFailedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductProgressEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductResultEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicQuestionDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiCallbackUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
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
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
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

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AiCallbackController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, ValidationConfig.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class, InternalApiProperties.class})
class AiCallbackControllerTest {

    private static final UUID DIAGNOSES_ID = UUID.fromString("01990000-0000-7000-8000-000000000001");
    private static final UUID PRODUCT_ID = UUID.fromString("01990000-0000-7000-8000-000000000002");
    private static final String URL = "/internal/v1/ai/products/" + PRODUCT_ID;
    private static final String COMMON_FIELDS = """
            "eventId": "event-1",
            "diagnosisId": "01990000-0000-7000-8000-000000000001",
            "productId": "01990000-0000-7000-8000-000000000002",
            "runId": "run-1",
            "sequence": 14""";

    // AI(#321) ProductResultEvent 형식. status·determination·riskLevel은 AI 값 그대로 소문자로 온다.
    private static final String RESULT_JSON = """
            {
              "eventType": "product_result",
              %s,
              "assessment": {
                "status": "completed",
                "resultStatus": "DIRECT_IMPORT_CERTIFICATION_REQUIRED",
                "summary": "사입해서 판매하려면 안전확인(KC)이 필요합니다.",
                "toolReviews": [
                  {
                    "toolName": "CHILDREN",
                    "status": "COMPLETED",
                    "message": null,
                    "findings": [
                      {
                        "subject": "안전확인 대상 여부",
                        "determination": "required",
                        "riskLevel": "high",
                        "summary": "안전확인이 필요합니다.",
                        "rationale": "권장연령 3-6세 기준으로 완구에 해당합니다.",
                        "legalSources": [{"sourceName": "국가법령정보센터", "lawName": "어린이제품 안전 특별법 시행규칙"}]
                      }
                    ]
                  }
                ],
                "requiredActions": ["안전확인(KC) 신고 후 판매"],
                "notices": []
              }
            }
            """.formatted(COMMON_FIELDS);

    @Value("${internal-api.token}")
    private String internalToken;

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AiCallbackUseCase aiCallbackUseCase;

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
    @DisplayName("내부 토큰 없이 콜백을 보내면 401과 COMMON-004 코드를 응답하고 결과를 반영하지 않는다.")
    void receiveCallback_withoutToken_thenUnauthorized() throws Exception {
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content(RESULT_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));

        then(aiCallbackUseCase).should(never()).handleResult(any());
    }

    @Test
    @DisplayName("결과 콜백을 받으면 결과 반영을 요청하고 200을 응답한다.")
    void receiveCallback_withResultEvent_thenHandleResult() throws Exception {
        // when
        mockMvc.perform(callback(RESULT_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        // then
        ArgumentCaptor<ProductResultEvent> captor = ArgumentCaptor.forClass(ProductResultEvent.class);
        then(aiCallbackUseCase).should().handleResult(captor.capture());

        ProductResultEvent event = captor.getValue();
        assertThat(event.productId()).isEqualTo(PRODUCT_ID);
        assertThat(event.diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(event.runId()).isEqualTo("run-1");
        assertThat(event.assessment().status()).isEqualTo(AssessmentStatus.COMPLETED);
        assertThat(event.assessment().resultStatus()).isEqualTo(ResultStatus.DIRECT_IMPORT_CERTIFICATION_REQUIRED);
        assertThat(event.assessment().toolReviews().getFirst().toolName()).isEqualTo(ToolName.CHILDREN);
        assertThat(event.assessment().toolReviews().getFirst().findings().getFirst().determination())
                .isEqualTo(Determination.REQUIRED);
    }

    @Test
    @DisplayName("진행 콜백을 받으면 진행 반영을 요청하고 200을 응답한다.")
    void receiveCallback_withProgressEvent_thenHandleProgress() throws Exception {
        // given: stage·stageStatus는 AI 값 그대로 소문자로 온다.
        String json = """
                {"eventType": "product_progress", %s, "stage": "tool_execution", "stageStatus": "started", "toolName": "CHILDREN"}"""
                .formatted(COMMON_FIELDS);

        // when
        mockMvc.perform(callback(json))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        // then
        ArgumentCaptor<ProductProgressEvent> captor = ArgumentCaptor.forClass(ProductProgressEvent.class);
        then(aiCallbackUseCase).should().handleProgress(captor.capture());

        ProductProgressEvent event = captor.getValue();
        assertThat(event.diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(event.productId()).isEqualTo(PRODUCT_ID);
        assertThat(event.sequence()).isEqualTo(14);
        assertThat(event.stage()).isEqualTo(PipelineStage.TOOL_EXECUTION);
        assertThat(event.stageStatus()).isEqualTo(StageStatus.STARTED);
        assertThat(event.toolName()).isEqualTo(ToolName.CHILDREN);
    }

    @Test
    @DisplayName("질문 콜백을 받으면 질문 반영을 요청하고 200을 응답한다.")
    void receiveCallback_withAwaitingInputEvent_thenHandleAwaitingInput() throws Exception {
        // given
        String json = """
                {"eventType": "product_awaiting_input", %s, "questionRound": 1,
                 "questions": [{"questionKey": "sales_type", "questionOrder": 1, "questionText": "구매대행으로 파나요?"}]}"""
                .formatted(COMMON_FIELDS);

        // when
        mockMvc.perform(callback(json))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        // then
        ArgumentCaptor<ProductAwaitingInputEvent> captor = ArgumentCaptor.forClass(ProductAwaitingInputEvent.class);
        then(aiCallbackUseCase).should().handleAwaitingInput(captor.capture());

        ProductAwaitingInputEvent event = captor.getValue();
        assertThat(event.diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(event.questionRound()).isEqualTo(1);
        assertThat(event.questions())
                .extracting(PublicQuestionDto::questionKey, PublicQuestionDto::questionText, PublicQuestionDto::helpText)
                .containsExactly(tuple("sales_type", "구매대행으로 파나요?", null));
    }

    @Test
    @DisplayName("실패 콜백을 받으면 실패 반영을 요청하고 200을 응답한다.")
    void receiveCallback_withFailedEvent_thenHandleFailed() throws Exception {
        // given: 실행 전에 실패하면 stage 없이 온다.
        String json = """
                {"eventType": "product_failed", %s, "stage": null,
                 "error": {"code": "AI_TIMEOUT", "message": "시간이 초과되었습니다.", "retryable": true}}"""
                .formatted(COMMON_FIELDS);

        // when
        mockMvc.perform(callback(json))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        // then
        ArgumentCaptor<ProductFailedEvent> captor = ArgumentCaptor.forClass(ProductFailedEvent.class);
        then(aiCallbackUseCase).should().handleFailed(captor.capture());

        ProductFailedEvent event = captor.getValue();
        assertThat(event.diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(event.stage()).isNull();
        assertThat(event.error().code()).isEqualTo("AI_TIMEOUT");
        assertThat(event.error().message()).isEqualTo("시간이 초과되었습니다.");
        assertThat(event.error().retryable()).isTrue();
    }

    @ParameterizedTest(name = "{0}")
    @ValueSource(strings = {
            """
            {"eventType": "product_progress", %s, "stageStatus": "started"}""",
            """
            {"eventType": "product_awaiting_input", %s, "questionRound": 1, "questions": []}""",
            """
            {"eventType": "product_failed", %s, "error": {"code": " ", "message": "시간이 초과되었습니다."}}"""
    })
    @DisplayName("진행·질문·실패 콜백의 필수 값이 비어 있으면 400과 COMMON-002 코드를 응답하고 반영을 요청하지 않는다.")
    void receiveCallback_withInvalidEvent_thenBadRequest(String template) throws Exception {
        mockMvc.perform(callback(template.formatted(COMMON_FIELDS)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));

        then(aiCallbackUseCase).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("결과 요약이 비어 있으면 400과 COMMON-002 코드, 필드 위치를 응답한다.")
    void receiveCallback_withBlankSummary_thenBadRequestWithFieldDetail() throws Exception {
        // given
        String json = RESULT_JSON.replace("\"사입해서 판매하려면 안전확인(KC)이 필요합니다.\"", "\" \"");

        // when & then
        mockMvc.perform(callback(json))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("assessment.summary"));

        then(aiCallbackUseCase).should(never()).handleResult(any());
    }

    @Test
    @DisplayName("진단서 ID가 없으면 AI가 보내는 JSON 키(diagnosisId)로 필드 위치를 응답한다.")
    void receiveCallback_withoutDiagnosesId_thenBadRequestWithJsonFieldName() throws Exception {
        // given
        String json = RESULT_JSON.replace("\"diagnosisId\": \"01990000-0000-7000-8000-000000000001\"", "\"diagnosisId\": null");

        // when & then
        mockMvc.perform(callback(json))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("diagnosisId"));

        then(aiCallbackUseCase).should(never()).handleResult(any());
    }

    private MockHttpServletRequestBuilder callback(String json) {
        return post(URL)
                .header(InternalTokenFilter.HEADER_NAME, internalToken)
                .contentType(MediaType.APPLICATION_JSON)
                .content(json);
    }
}
