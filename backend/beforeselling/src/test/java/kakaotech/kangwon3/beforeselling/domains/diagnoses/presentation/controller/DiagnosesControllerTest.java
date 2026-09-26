package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.DiagnosesUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
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
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.web.OAuth2AuthorizedClientRepository;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(DiagnosesController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class})
class DiagnosesControllerTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final String BASE_URL = "/api/v1/diagnoses";
    private static final String S3_URL_PREFIX = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/";

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private DiagnosesUseCase diagnosesUseCase;

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
    @DisplayName("인증 없이 진단을 요청하면 401과 COMMON-004 코드를 응답한다.")
    void createDiagnoses_withoutAuthentication_thenUnauthorized() throws Exception {
        mockMvc.perform(post(BASE_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(urlTypeRequest())))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("상세페이지 URL로 진단을 요청하면 생성된 진단서 ID를 응답한다.")
    void createDiagnoses_withUrlType_thenReturnDiagnosesId() throws Exception {
        // given
        given(diagnosesUseCase.createDiagnoses(any(UUID.class), any()))
                .willReturn(new DiagnosesCreateResponse(DIAGNOSES_ID));

        // when & then
        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(urlTypeRequest())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.diagnosesId").value(DIAGNOSES_ID.toString()));

        then(diagnosesUseCase).should().createDiagnoses(eq(USER_ID), any());
    }

    @Test
    @DisplayName("제품명 없이 진단을 요청하면 400과 COMMON-002 코드를 응답한다.")
    void createDiagnoses_withoutProductName_thenBadRequest() throws Exception {
        Map<String, Object> product = urlTypeProduct();
        product.remove("productName");
        Map<String, Object> request = wrap(product);

        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("URL 등록 방식인데 상세페이지 URL이 없으면 400과 COMMON-002 코드를 응답한다.")
    void createDiagnoses_withUrlTypeAndNoSourceUrl_thenBadRequest() throws Exception {
        Map<String, Object> product = urlTypeProduct();
        product.remove("sourceUrl");
        Map<String, Object> request = wrap(product);

        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("텍스트·이미지 등록 방식인데 본문과 이미지가 모두 없으면 400과 COMMON-002 코드를 응답한다.")
    void createDiagnoses_withTextImageTypeAndNoContent_thenBadRequest() throws Exception {
        Map<String, Object> product = new HashMap<>();
        product.put("productName", "대나무 헬리콥터");
        product.put("sourceType", SourceType.TEXT_IMAGE.name());
        Map<String, Object> request = wrap(product);

        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("상세페이지 이미지 키로 진단을 요청하면 생성된 진단서 ID를 응답한다.")
    void createDiagnoses_withImageKeys_thenReturnDiagnosesId() throws Exception {
        // given
        given(diagnosesUseCase.createDiagnoses(any(UUID.class), any()))
                .willReturn(new DiagnosesCreateResponse(DIAGNOSES_ID));

        Map<String, Object> product = new HashMap<>();
        product.put("productName", "대나무 헬리콥터");
        product.put("sourceType", SourceType.TEXT_IMAGE.name());
        product.put("imageKeys", List.of(
                "product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));
        Map<String, Object> request = wrap(product);

        // when & then
        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.diagnosesId").value(DIAGNOSES_ID.toString()));
    }

    @Test
    @DisplayName("본인의 진단서를 단건 조회하면 진단서 상세 정보를 응답한다.")
    void getDiagnoses_thenReturnDetail() throws Exception {
        // given
        given(diagnosesUseCase.getDiagnoses(USER_ID, DIAGNOSES_ID)).willReturn(detailResponse());

        // when & then
        mockMvc.perform(get(BASE_URL + "/{diagnosesId}", DIAGNOSES_ID)
                        .with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.diagnosesId").value(DIAGNOSES_ID.toString()))
                .andExpect(jsonPath("$.data.processingStatus").value("PENDING"))
                .andExpect(jsonPath("$.data.products.length()").value(1))
                .andExpect(jsonPath("$.data.products[0].productName").value("대나무 헬리콥터"))
                .andExpect(jsonPath("$.data.products[0].resultStatus").doesNotExist())
                .andExpect(jsonPath("$.data.products[0].imageUrls.length()").value(2));
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 404와 COMMON-006 코드를 응답한다.")
    void getDiagnoses_withOtherUsersDiagnoses_thenNotFound() throws Exception {
        // given: 타인 소유 리소스도 404로 응답한다(CODE_CONVENTION.md — IDOR 방지)
        willThrow(new BaseException(CommonResponseCode.NOT_FOUND))
                .given(diagnosesUseCase).getDiagnoses(any(UUID.class), any(UUID.class));

        // when & then
        mockMvc.perform(get(BASE_URL + "/{diagnosesId}", DIAGNOSES_ID)
                        .with(authentication(loginUser())))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("COMMON-006"));
    }

    private Authentication loginUser() {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(USER_ID, Role.USER),
                null,
                List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }

    private Map<String, Object> urlTypeRequest() {
        return wrap(urlTypeProduct());
    }

    private Map<String, Object> urlTypeProduct() {
        Map<String, Object> product = new HashMap<>();
        product.put("productName", "대나무 헬리콥터");
        product.put("productImageKey", "product-main/1/uuid_thumbnail.jpg");
        product.put("sourceType", SourceType.URL.name());
        product.put("sourceUrl", "https://ko.aliexpress.com/item/100500628491");
        return product;
    }

    private Map<String, Object> wrap(Map<String, Object>... products) {
        Map<String, Object> request = new HashMap<>();
        request.put("products", List.of(products));
        return request;
    }

    private DiagnosesDetailResponse detailResponse() {
        ProductResponse product = new ProductResponse(
                PRODUCT_ID, 0, "대나무 헬리콥터", S3_URL_PREFIX + "product-main/1/uuid_thumbnail.jpg",
                SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null,
                List.of(S3_URL_PREFIX + "product-detail/1/uuid_a1.jpg", S3_URL_PREFIX + "product-detail/1/uuid_a2.jpg"),
                ProcessingStatus.PENDING, null, null);

        return new DiagnosesDetailResponse(
                DIAGNOSES_ID, ProcessingStatus.PENDING, List.of(product),
                LocalDateTime.now(), LocalDateTime.now());
    }

}
