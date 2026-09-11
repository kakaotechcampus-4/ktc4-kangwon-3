package kakaotech.kangwon3.beforeselling.global.infra.s3.presentation.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.config.SecurityConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.JwtProperties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileResponseCode;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileType;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3PresignedUrlProvider;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlRequest;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
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

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(S3PresignController.class)
@ActiveProfiles("test")
@Import({SecurityConfig.class, ApiResponseWriter.class})
@EnableConfigurationProperties({AppProperties.class, JwtProperties.class})
class S3PresignControllerTest {

    @Autowired
    private MockMvc mockMvc;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @MockitoBean
    private S3PresignedUrlProvider s3PresignedUrlProvider;

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

    private static Authentication authenticationOf(Long userId) {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(userId, Role.USER), null, List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }

    @Test
    @DisplayName("인증 없이 Presigned URL을 요청하면 401과 COMMON-004 코드를 응답한다.")
    void issuePresignedUrls_withoutAuthentication_thenUnauthorized() throws Exception {
        PresignedUrlRequest request = new PresignedUrlRequest(List.of(
                new PresignedUrlRequest.FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", "image/jpeg", 1024)));

        mockMvc.perform(post("/api/v1/presigned-url")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("COMMON-004"));
    }

    @Test
    @DisplayName("인증된 사용자가 올바른 요청을 보내면 Presigned URL 목록을 응답한다.")
    void issuePresignedUrls_withValidRequest_thenReturnPresignedUrls() throws Exception {
        // given
        PresignedUrlRequest request = new PresignedUrlRequest(List.of(
                new PresignedUrlRequest.FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", "image/jpeg", 1024)));
        PresignedUrlResponse response = new PresignedUrlResponse(List.of(
                new PresignedUrlResponse.PresignedFile(
                        "thumb.jpg",
                        "product-main/1/uuid_thumb.jpg",
                        "https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1/uuid_thumb.jpg?X-Amz-Signature=...",
                        "https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1/uuid_thumb.jpg")));
        given(s3PresignedUrlProvider.issuePresignedUrls(eq(1L), any())).willReturn(response);

        // when & then
        mockMvc.perform(post("/api/v1/presigned-url")
                        .with(authentication(authenticationOf(1L)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value("OK"))
                .andExpect(jsonPath("$.data.files[0].fileName").value("thumb.jpg"))
                .andExpect(jsonPath("$.data.files[0].key").value("product-main/1/uuid_thumb.jpg"))
                .andExpect(jsonPath("$.data.files[0].fileUrl").value(
                        "https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1/uuid_thumb.jpg"));
        then(s3PresignedUrlProvider).should().issuePresignedUrls(eq(1L), any());
    }

    @Test
    @DisplayName("파일 목록이 비어있으면 400과 COMMON-002 코드를 응답한다.")
    void issuePresignedUrls_withEmptyFiles_thenBadRequest() throws Exception {
        PresignedUrlRequest request = new PresignedUrlRequest(List.of());

        mockMvc.perform(post("/api/v1/presigned-url")
                        .with(authentication(authenticationOf(1L)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("COMMON-002"));
    }

    @Test
    @DisplayName("지원하지 않는 확장자를 요청하면 400과 FILE-001 코드를 응답한다.")
    void issuePresignedUrls_withUnsupportedExtension_thenBadRequest() throws Exception {
        // given
        PresignedUrlRequest request = new PresignedUrlRequest(List.of(
                new PresignedUrlRequest.FileMeta(FileType.PRODUCT_MAIN, "malware.exe", "application/octet-stream", 1024)));
        given(s3PresignedUrlProvider.issuePresignedUrls(eq(1L), any()))
                .willThrow(new BaseException(FileResponseCode.NOT_SUPPORTED_EXTENSION));

        // when & then
        mockMvc.perform(post("/api/v1/presigned-url")
                        .with(authentication(authenticationOf(1L)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("FILE-001"));
    }
}
