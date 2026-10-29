package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.ProductAnswerRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.FindingLegalSourceResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductFindingResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductFailureResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductToolReviewResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.ProductUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller.ProductController;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.common.PageInfo;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.InternalApiProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.cookie.OAuth2RedirectCookieProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ProductController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class, InternalApiProperties.class})
class ProductControllerTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final UUID DIAGNOSES_ID = UUID.randomUUID(); // 추가
    private static final UUID TOOL_REVIEW_ID = UUID.randomUUID();
    private static final UUID FINDING_ID = UUID.randomUUID();
    private static final UUID LEGAL_SOURCE_ID = UUID.randomUUID();
    private static final UUID QUESTION_ID = UUID.randomUUID();
    private static final String BASE_URL = "/api/v1/products";
    private static final String ANSWERS_URL = BASE_URL + "/{productId}/answers";
    private static final String S3_URL_PREFIX = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/";

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ProductUseCase productUseCase;

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
    @DisplayName("인증 없이 상품 목록을 조회하면 401과 COMMON-004 코드를 응답한다.")
    void getProductList_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(get(BASE_URL))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("페이징 조건 없이 목록을 조회하면 첫 페이지를 최신순으로 조회한다.")
    void getProductList_withDefaultParameters_thenSortByLatest() throws Exception {
        // given
        given(productUseCase.getProductList(any(UUID.class), any(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL).with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.products[0].diagnosesId").value(DIAGNOSES_ID.toString())) // 추가
                .andExpect(jsonPath("$.data.products[0].productName").value("대나무 헬리콥터"))
                .andExpect(jsonPath("$.data.products[0].sourceType").value("URL"))
                .andExpect(jsonPath("$.data.pageInfo.page").value(0))
                .andExpect(jsonPath("$.data.pageInfo.hasNext").value(false));

        // then
        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        then(productUseCase).should()
                .getProductList(eq(USER_ID), isNull(), isNull(), pageableCaptor.capture());
        Pageable pageable = pageableCaptor.getValue();

        assertThat(pageable.getPageNumber()).isZero();
        assertThat(pageable.getPageSize()).isEqualTo(10);
        assertThat(pageable.getSort()).isEqualTo(Sort.by(Sort.Direction.DESC, "createdAt"));
    }

    @Test
    @DisplayName("실패한 상품이 있으면 목록 응답에 실패 단계·오류 코드·메시지·재시도 여부가 담긴다.")
    void getProductList_withFailedProduct_thenIncludeFailure() throws Exception {
        // given
        given(productUseCase.getProductList(any(UUID.class), any(), any(), any())).willReturn(failedListResponse());

        // when & then
        mockMvc.perform(get(BASE_URL).with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.products[0].processingStatus").value("FAILED"))
                .andExpect(jsonPath("$.data.products[0].failure.failedStage").value("TOOL_EXECUTION"))
                .andExpect(jsonPath("$.data.products[0].failure.errorCode").value("AI_TIMEOUT"))
                .andExpect(jsonPath("$.data.products[0].failure.errorMessage").value("진단 시간이 초과되었습니다."))
                .andExpect(jsonPath("$.data.products[0].failure.retryable").value(true));
    }

    @Test
    @DisplayName("오래된순으로 목록을 조회하면 등록 시각 오름차순으로 조회한다.")
    void getProductList_withOldestSortType_thenSortByAscending() throws Exception {
        // given
        given(productUseCase.getProductList(any(UUID.class), any(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL)
                        .param("sortType", "OLDEST")
                        .with(authentication(loginUser())))
                .andExpect(status().isOk());

        // then
        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        then(productUseCase).should()
                .getProductList(any(UUID.class), any(), any(), pageableCaptor.capture());
        assertThat(pageableCaptor.getValue().getSort())
                .isEqualTo(Sort.by(Sort.Direction.ASC, "createdAt"));
    }

    @Test
    @DisplayName("결과 필터를 지정해 목록을 조회하면 해당 필터가 함께 전달된다.")
    void getProductList_withResultStatus_thenPassFilter() throws Exception {
        // given
        given(productUseCase.getProductList(any(UUID.class), any(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL)
                        .param("resultStatus", ResultStatus.RECHECK_REQUIRED.name())
                        .with(authentication(loginUser())))
                .andExpect(status().isOk());

        // then
        then(productUseCase).should()
                .getProductList(eq(USER_ID), eq(ResultStatus.RECHECK_REQUIRED), isNull(), any(Pageable.class));
    }

    @Test
    @DisplayName("상품명 검색어를 지정해 목록을 조회하면 검색어가 함께 전달된다.")
    void getProductList_withKeyword_thenPassKeyword() throws Exception {
        // given
        given(productUseCase.getProductList(any(UUID.class), any(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL)
                        .param("keyword", "헬리콥터")
                        .with(authentication(loginUser())))
                .andExpect(status().isOk());

        // then
        then(productUseCase).should()
                .getProductList(eq(USER_ID), isNull(), eq("헬리콥터"), any(Pageable.class));
    }

    @Test
    @DisplayName("페이지 번호를 음수로 요청하면 어떤 값이 잘못되었는지 함께 응답한다.")
    void getProductList_withNegativePage_thenBadRequestWithFieldDetail() throws Exception {
        mockMvc.perform(get(BASE_URL)
                        .param("page", "-1")
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("page"));
    }

    @Test
    @DisplayName("페이지 크기를 0으로 요청하면 어떤 값이 잘못되었는지 함께 응답한다.")
    void getProductList_withZeroSize_thenBadRequestWithFieldDetail() throws Exception {
        mockMvc.perform(get(BASE_URL)
                        .param("size", "0")
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("size"))
                .andExpect(jsonPath("$.details[0].message").value("페이지 크기는 1 이상이어야 합니다."));
    }

    @Test
    @DisplayName("페이지 크기가 허용 범위를 넘으면 어떤 값이 잘못되었는지 함께 응답한다.")
    void getProductList_withTooLargeSize_thenBadRequestWithFieldDetail() throws Exception {
        mockMvc.perform(get(BASE_URL)
                        .param("size", "101")
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("size"))
                .andExpect(jsonPath("$.details[0].message").value("페이지 크기는 100 이하여야 합니다."));
    }

    @Test
    @DisplayName("지원하지 않는 정렬 기준으로 요청하면 어떤 값이 잘못되었는지 함께 응답한다.")
    void getProductList_withUnknownSortType_thenBadRequestWithFieldDetail() throws Exception {
        mockMvc.perform(get(BASE_URL)
                        .param("sortType", "UNKNOWN")
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("sortType"));
    }

    @Test
    @DisplayName("검색어가 100자를 넘으면 어떤 값이 잘못되었는지 함께 응답한다.")
    void getProductList_withTooLongKeyword_thenBadRequestWithFieldDetail() throws Exception {
        mockMvc.perform(get(BASE_URL)
                        .param("keyword", "가".repeat(101))
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("keyword"))
                .andExpect(jsonPath("$.details[0].message").value("검색어는 100자를 넘을 수 없습니다."));
    }

    @Test
    @DisplayName("지원하지 않는 결과 필터로 요청하면 어떤 값이 잘못되었는지 함께 응답한다.")
    void getProductList_withUnknownResultStatus_thenBadRequestWithFieldDetail() throws Exception {
        mockMvc.perform(get(BASE_URL)
                        .param("resultStatus", "UNKNOWN")
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("resultStatus"));
    }

    @Test
    @DisplayName("인증 없이 상품을 단건 조회하면 401과 COMMON-004 코드를 응답한다.")
    void getProduct_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(get(BASE_URL + "/{productId}", PRODUCT_ID))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("본인의 상품을 단건 조회하면 진단서 상세의 상품 항목과 같은 형태로 응답한다.")
    void getProduct_thenReturnProductResponse() throws Exception {
        // given
        given(productUseCase.getProduct(USER_ID, PRODUCT_ID)).willReturn(productResponse());

        // when & then
        mockMvc.perform(get(BASE_URL + "/{productId}", PRODUCT_ID)
                        .with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.productId").value(PRODUCT_ID.toString()))
                .andExpect(jsonPath("$.data.diagnosesId").value(DIAGNOSES_ID.toString()))
                .andExpect(jsonPath("$.data.productName").value("대나무 헬리콥터"))
                .andExpect(jsonPath("$.data.sourceType").value("URL"))
                .andExpect(jsonPath("$.data.imageUrls[0]").value(S3_URL_PREFIX + "product-detail/1/uuid_a1.jpg"))
                .andExpect(jsonPath("$.data.resultStatus").value("RECHECK_REQUIRED"))
                .andExpect(jsonPath("$.data.summary").value("배터리 표시 항목 재확인이 필요합니다."))
                .andExpect(jsonPath("$.data.assessmentStatus").value("COMPLETED"))
                .andExpect(jsonPath("$.data.toolReviews[0].productToolReviewId").value(TOOL_REVIEW_ID.toString()))
                .andExpect(jsonPath("$.data.toolReviews[0].toolName").value("CHILDREN"))
                .andExpect(jsonPath("$.data.toolReviews[0].findings[0].productFindingId").value(FINDING_ID.toString()))
                .andExpect(jsonPath("$.data.toolReviews[0].findings[0].determination").value("POSSIBLY_REQUIRED"))
                .andExpect(jsonPath("$.data.toolReviews[0].findings[0].legalSources[0].findingLegalSourceId")
                        .value(LEGAL_SOURCE_ID.toString()))
                .andExpect(jsonPath("$.data.toolReviews[0].findings[0].legalSources[0].article").value("별표 2"))
                .andExpect(jsonPath("$.data.requiredActions[0]").value("배터리 표시 보완"))
                .andExpect(jsonPath("$.data.notices[0]").value("구매대행 상품은 이 조문의 적용을 받지 않습니다."));
    }

    @Test
    @DisplayName("없는 상품이나 다른 사용자의 상품을 단건 조회하면 404와 COMMON-006 코드를 응답한다.")
    void getProduct_withUnknownId_thenNotFound() throws Exception {
        // given
        given(productUseCase.getProduct(any(UUID.class), any(UUID.class)))
                .willThrow(new BaseException(CommonResponseCode.NOT_FOUND));

        // when & then
        mockMvc.perform(get(BASE_URL + "/{productId}", PRODUCT_ID)
                        .with(authentication(loginUser())))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("COMMON-006"));
    }

    @Test
    @DisplayName("UUID 형식이 아닌 상품 id로 단건 조회하면 400을 응답한다.")
    void getProduct_withMalformedId_thenBadRequest() throws Exception {
        mockMvc.perform(get(BASE_URL + "/{productId}", "not-a-uuid")
                        .with(authentication(loginUser())))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("인증 없이 답변을 제출하면 401과 COMMON-004 코드를 응답한다.")
    void answerQuestions_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answersBody(QUESTION_ID, "구매대행")))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("질문에 답하면 성공 응답을 받고 답변이 그대로 전달된다.")
    void answerQuestions_thenSuccess() throws Exception {
        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answersBody(QUESTION_ID, "구매대행")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        then(productUseCase).should().answerQuestions(USER_ID, PRODUCT_ID,
                new ProductAnswerRequest(List.of(new ProductAnswerRequest.Answer(QUESTION_ID, "구매대행"))));
    }

    @Test
    @DisplayName("같은 질문에 두 번 답하면 400과 COMMON-002 코드를 응답하고 답변을 처리하지 않는다.")
    void answerQuestions_withDuplicateQuestionId_thenBadRequest() throws Exception {
        String body = """
                {"answers": [
                  {"questionId": "%s", "answerText": "구매대행"},
                  {"questionId": "%s", "answerText": "사입"}
                ]}
                """.formatted(QUESTION_ID, QUESTION_ID);

        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"))
                .andExpect(jsonPath("$.details[0].field").value("questionIdsUnique"));

        then(productUseCase).should(never()).answerQuestions(any(), any(), any());
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "{\"answers\": []}",
            "{\"answers\": [{\"questionId\": null, \"answerText\": \"구매대행\"}]}",
            "{\"answers\": [{\"questionId\": \"0199f4e2-6b3a-7c00-8000-000000000001\", \"answerText\": \" \"}]}"
    })
    @DisplayName("답변이 없거나 질문 ID·답변 내용이 비어 있으면 400과 COMMON-002 코드를 응답한다.")
    void answerQuestions_withInvalidBody_thenBadRequest(String body) throws Exception {
        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));

        then(productUseCase).should(never()).answerQuestions(any(), any(), any());
    }

    @Test
    @DisplayName("답변이 500자를 넘으면 400과 COMMON-002 코드를 응답한다.")
    void answerQuestions_withTooLongAnswer_thenBadRequest() throws Exception {
        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answersBody(QUESTION_ID, "가".repeat(501))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("답변 대기가 아닌 상품에 답하면 409와 COMMON-010 코드를 응답한다.")
    void answerQuestions_whenNotAwaitingInput_thenConflict() throws Exception {
        // given
        willThrow(new BaseException(CommonResponseCode.CONFLICT))
                .given(productUseCase).answerQuestions(any(), any(), any());

        // when & then
        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answersBody(QUESTION_ID, "구매대행")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("COMMON-010"));
    }

    @Test
    @DisplayName("존재하지 않는 상품에 답하면 404와 COMMON-006 코드를 응답한다.")
    void answerQuestions_withUnknownId_thenNotFound() throws Exception {
        // given
        willThrow(new BaseException(CommonResponseCode.NOT_FOUND))
                .given(productUseCase).answerQuestions(any(), any(), any());

        // when & then
        mockMvc.perform(post(ANSWERS_URL, PRODUCT_ID)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answersBody(QUESTION_ID, "구매대행")))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("COMMON-006"));
    }

    @Test
    @DisplayName("본인의 상품을 삭제하면 성공 응답을 받는다.")
    void removeProduct_thenSuccess() throws Exception {
        mockMvc.perform(delete(BASE_URL + "/{productId}", PRODUCT_ID)
                        .with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        then(productUseCase).should().removeProduct(USER_ID, PRODUCT_ID);
    }

    @Test
    @DisplayName("존재하지 않는 상품을 삭제하면 404와 COMMON-006 코드를 응답한다.")
    void removeProduct_withUnknownId_thenNotFound() throws Exception {
        // given
        willThrow(new BaseException(CommonResponseCode.NOT_FOUND))
                .given(productUseCase).removeProduct(any(UUID.class), any(UUID.class));

        // when & then
        mockMvc.perform(delete(BASE_URL + "/{productId}", PRODUCT_ID)
                        .with(authentication(loginUser())))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("COMMON-006"));
    }

    private String answersBody(UUID questionId, String answerText) {
        return """
                {"answers": [{"questionId": "%s", "answerText": "%s"}]}
                """.formatted(questionId, answerText);
    }

    private Authentication loginUser() {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(USER_ID, Role.USER),
                null,
                List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }

    private ProductListResponse listResponse() {
        // 수정: DIAGNOSES_ID 인자 추가
        ProductSummaryResponse summary = new ProductSummaryResponse(
                PRODUCT_ID, DIAGNOSES_ID, "대나무 헬리콥터", S3_URL_PREFIX + "product-main/1/uuid_thumbnail.jpg",
                SourceType.URL, ProcessingStatus.PENDING, null, null, LocalDateTime.now());

        return new ProductListResponse(List.of(summary), new PageInfo(0, 10, 1, 1, false));
    }

    private ProductListResponse failedListResponse() {
        ProductSummaryResponse summary = new ProductSummaryResponse(
                PRODUCT_ID, DIAGNOSES_ID, "대나무 헬리콥터", null,
                SourceType.URL, ProcessingStatus.FAILED, null,
                new ProductFailureResponse(PipelineStage.TOOL_EXECUTION, "AI_TIMEOUT", "진단 시간이 초과되었습니다.", true),
                LocalDateTime.now());

        return new ProductListResponse(List.of(summary), new PageInfo(0, 10, 1, 1, false));
    }

    private ProductResponse productResponse() {
        return new ProductResponse(
                PRODUCT_ID, DIAGNOSES_ID, "대나무 헬리콥터", S3_URL_PREFIX + "product-main/1/uuid_thumbnail.jpg",
                SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null,
                List.of(S3_URL_PREFIX + "product-detail/1/uuid_a1.jpg"),
                ProcessingStatus.COMPLETED, List.of(), List.of(), null,
                AssessmentStatus.COMPLETED, ResultStatus.RECHECK_REQUIRED,
                "배터리 표시 항목 재확인이 필요합니다.",
                List.of(new ProductToolReviewResponse(TOOL_REVIEW_ID, ToolName.CHILDREN, ToolReviewStatus.COMPLETED, null,
                        List.of(new ProductFindingResponse(FINDING_ID, "표시사항", Determination.POSSIBLY_REQUIRED,
                                RiskLevel.MEDIUM, "배터리 표시를 확인해야 합니다.", "상세페이지에 배터리 표기가 없습니다.",
                                List.of(new FindingLegalSourceResponse(LEGAL_SOURCE_ID, "국가법령정보센터",
                                        "어린이제품 안전 특별법 시행규칙", "별표 2", null, null, "2026-09-03")))))),
                List.of("배터리 표시 보완"),
                List.of("구매대행 상품은 이 조문의 적용을 받지 않습니다."));
    }
}