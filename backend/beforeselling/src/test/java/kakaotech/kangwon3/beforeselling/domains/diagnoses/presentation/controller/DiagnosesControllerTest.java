package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.DiagnosesUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
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
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
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
@Import({SecurityConfig.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class})
class DiagnosesControllerTest {

    private static final String BASE_URL = "/api/v1/diagnoses";

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
    @DisplayName("상세페이지 URL로 진단을 요청하면 성공 응답을 받는다.")
    void createDiagnoses_withUrlType_thenSuccess() throws Exception {
        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(urlTypeRequest())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        then(diagnosesUseCase).should().createDiagnoses(eq(1L), any());
    }

    @Test
    @DisplayName("제품명 없이 진단을 요청하면 400과 COMMON-002 코드를 응답한다.")
    void createDiagnoses_withoutProductName_thenBadRequest() throws Exception {
        Map<String, Object> request = urlTypeRequest();
        request.remove("productName");

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
        Map<String, Object> request = urlTypeRequest();
        request.remove("sourceUrl");

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
        Map<String, Object> request = new HashMap<>();
        request.put("productName", "대나무 헬리콥터");
        request.put("sourceType", SourceType.TEXT_IMAGE.name());

        mockMvc.perform(post(BASE_URL)
                        .with(authentication(loginUser()))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("본인의 진단서를 단건 조회하면 진단서 상세 정보를 응답한다.")
    void getDiagnoses_thenReturnDetail() throws Exception {
        // given
        given(diagnosesUseCase.getDiagnoses(1L, 1L)).willReturn(detailResponse());

        // when & then
        mockMvc.perform(get(BASE_URL + "/{diagnosesId}", 1L)
                        .with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.diagnosesId").value(1))
                .andExpect(jsonPath("$.data.productName").value("대나무 헬리콥터"))
                .andExpect(jsonPath("$.data.processingStatus").value("PENDING"))
                .andExpect(jsonPath("$.data.resultStatus").doesNotExist())
                .andExpect(jsonPath("$.data.imageUrls.length()").value(2));
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 403과 COMMON-005 코드를 응답한다.")
    void getDiagnoses_withOtherUsersDiagnoses_thenForbidden() throws Exception {
        // given
        willThrow(new BaseException(CommonResponseCode.FORBIDDEN))
                .given(diagnosesUseCase).getDiagnoses(anyLong(), anyLong());

        // when & then
        mockMvc.perform(get(BASE_URL + "/{diagnosesId}", 1L)
                        .with(authentication(loginUser())))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("COMMON-005"));
    }

    @Test
    @DisplayName("페이징 조건 없이 목록을 조회하면 첫 페이지를 최신순으로 조회한다.")
    void getDiagnosesList_withDefaultParameters_thenSortByLatest() throws Exception {
        // given
        given(diagnosesUseCase.getDiagnosesList(anyLong(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL).with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.diagnoses[0].productName").value("대나무 헬리콥터"))
                .andExpect(jsonPath("$.data.pageInfo.page").value(0))
                .andExpect(jsonPath("$.data.pageInfo.hasNext").value(false));

        // then
        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        then(diagnosesUseCase).should().getDiagnosesList(eq(1L), isNull(), pageableCaptor.capture());
        Pageable pageable = pageableCaptor.getValue();

        assertThat(pageable.getPageNumber()).isZero();
        assertThat(pageable.getPageSize()).isEqualTo(10);
        assertThat(pageable.getSort()).isEqualTo(Sort.by(Sort.Direction.DESC, "createdAt"));
    }

    @Test
    @DisplayName("오래된순으로 목록을 조회하면 등록 시각 오름차순으로 조회한다.")
    void getDiagnosesList_withOldestSortType_thenSortByAscending() throws Exception {
        // given
        given(diagnosesUseCase.getDiagnosesList(anyLong(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL)
                        .param("sortType", "OLDEST")
                        .with(authentication(loginUser())))
                .andExpect(status().isOk());

        // then
        ArgumentCaptor<Pageable> pageableCaptor = ArgumentCaptor.forClass(Pageable.class);
        then(diagnosesUseCase).should().getDiagnosesList(anyLong(), any(), pageableCaptor.capture());
        assertThat(pageableCaptor.getValue().getSort())
                .isEqualTo(Sort.by(Sort.Direction.ASC, "createdAt"));
    }

    @Test
    @DisplayName("결과 필터를 지정해 목록을 조회하면 해당 필터가 함께 전달된다.")
    void getDiagnosesList_withResultStatus_thenPassFilter() throws Exception {
        // given
        given(diagnosesUseCase.getDiagnosesList(anyLong(), any(), any())).willReturn(listResponse());

        // when
        mockMvc.perform(get(BASE_URL)
                        .param("resultStatus", ResultStatus.RECHECK_REQUIRED.name())
                        .with(authentication(loginUser())))
                .andExpect(status().isOk());

        // then
        then(diagnosesUseCase).should()
                .getDiagnosesList(eq(1L), eq(ResultStatus.RECHECK_REQUIRED), any(Pageable.class));
    }

    @Test
    @DisplayName("본인의 진단서를 삭제하면 성공 응답을 받는다.")
    void removeDiagnoses_thenSuccess() throws Exception {
        mockMvc.perform(delete(BASE_URL + "/{diagnosesId}", 1L)
                        .with(authentication(loginUser())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"));

        then(diagnosesUseCase).should().removeDiagnoses(1L, 1L);
    }

    @Test
    @DisplayName("존재하지 않는 진단서를 삭제하면 404와 COMMON-006 코드를 응답한다.")
    void removeDiagnoses_withUnknownId_thenNotFound() throws Exception {
        // given
        willThrow(new BaseException(CommonResponseCode.NOT_FOUND))
                .given(diagnosesUseCase).removeDiagnoses(anyLong(), anyLong());

        // when & then
        mockMvc.perform(delete(BASE_URL + "/{diagnosesId}", 1L)
                        .with(authentication(loginUser())))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("COMMON-006"));
    }

    private Authentication loginUser() {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(1L, Role.USER),
                null,
                List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }

    private Map<String, Object> urlTypeRequest() {
        Map<String, Object> request = new HashMap<>();
        request.put("productName", "대나무 헬리콥터");
        request.put("productImageUrl", "https://image.com/thumbnail");
        request.put("sourceType", SourceType.URL.name());
        request.put("sourceUrl", "https://ko.aliexpress.com/item/100500628491");
        return request;
    }

    private DiagnosesDetailResponse detailResponse() {
        return new DiagnosesDetailResponse(
                1L, "대나무 헬리콥터", "https://image.com/thumbnail",
                SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null,
                List.of("https://image.com/1", "https://image.com/2"),
                ProcessingStatus.PENDING, null, null,
                LocalDateTime.now(), LocalDateTime.now());
    }

    private DiagnosesListResponse listResponse() {
        DiagnosesSummaryResponse summary = new DiagnosesSummaryResponse(
                1L, "대나무 헬리콥터", "https://image.com/thumbnail",
                ProcessingStatus.PENDING, null, LocalDateTime.now());

        return new DiagnosesListResponse(
                List.of(summary),
                new DiagnosesListResponse.PageInfo(0, 10, 1, 1, false));
    }
}
