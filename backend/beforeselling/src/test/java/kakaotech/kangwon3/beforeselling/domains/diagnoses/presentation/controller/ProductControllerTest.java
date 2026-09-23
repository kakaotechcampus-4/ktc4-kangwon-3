package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.ProductSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.ProductUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.common.PageInfo;
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
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
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
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ProductController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, OAuth2RedirectCookieProvider.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class})
class ProductControllerTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final String BASE_URL = "/api/v1/products";
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

    private Authentication loginUser() {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(USER_ID, Role.USER),
                null,
                List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }

    private ProductListResponse listResponse() {
        ProductSummaryResponse summary = new ProductSummaryResponse(
                PRODUCT_ID, "대나무 헬리콥터", S3_URL_PREFIX + "product-main/1/uuid_thumbnail.jpg",
                SourceType.URL, ProcessingStatus.PENDING, null, LocalDateTime.now());

        return new ProductListResponse(List.of(summary), new PageInfo(0, 10, 1, 1, false));
    }
}
