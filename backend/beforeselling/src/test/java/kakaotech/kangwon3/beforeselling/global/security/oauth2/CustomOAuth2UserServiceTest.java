package kakaotech.kangwon3.beforeselling.global.security.oauth2;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserLookupResult;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.oauth2.core.OAuth2AccessToken;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.time.Instant;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

/**
 * 제공자 사용자 정보 조회(HTTP)는 MockRestServiceServer로 대체하고, 응답을 회원으로 바꾸는 과정을 검증한다.
 */
@ExtendWith(MockitoExtension.class)
class CustomOAuth2UserServiceTest {

    private static final String USER_INFO_URI = "https://provider.example.com/v1/user/me";
    private static final String ACCESS_TOKEN = "provider-access-token";
    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private UserService userService;

    private CustomOAuth2UserService customOAuth2UserService;
    private MockRestServiceServer providerServer;

    @BeforeEach
    void setUp() {
        RestTemplate restTemplate = new RestTemplate();
        providerServer = MockRestServiceServer.bindTo(restTemplate).build();
        customOAuth2UserService = new CustomOAuth2UserService(userService);
        customOAuth2UserService.setRestOperations(restTemplate);
    }

    @Test
    @DisplayName("처음 로그인한 카카오 사용자는 회원으로 가입되고 신규 가입으로 표시된다.")
    void loadUser_withNewKakaoUser_thenSignupAndMarkNew() {
        // given
        respondUserInfo("""
                {"id": 12345, "kakao_account": {"email": "user@example.com", "profile": {"nickname": "홍길동"}}}
                """);
        given(userService.getOrCreateUser(SocialProvider.KAKAO, "12345", "user@example.com", "홍길동"))
                .willReturn(new UserLookupResult(userWithId(), true));

        // when
        OAuth2User oAuth2User = customOAuth2UserService.loadUser(userRequest("kakao", "id"));

        // then
        assertThat(oAuth2User).isInstanceOf(CustomOAuth2User.class);
        CustomOAuth2User customUser = (CustomOAuth2User) oAuth2User;
        assertThat(customUser.userId()).isEqualTo(USER_ID);
        assertThat(customUser.role()).isEqualTo(Role.USER);
        assertThat(customUser.isNewUser()).isTrue();
        assertThat(customUser.getName()).isEqualTo(USER_ID.toString());
        assertThat(customUser.getAttributes()).containsEntry("id", 12345);
        providerServer.verify();
    }

    @Test
    @DisplayName("이미 가입한 사용자는 신규 가입으로 표시되지 않는다.")
    void loadUser_withExistingUser_thenNotMarkedNew() {
        // given
        respondUserInfo("""
                {"id": 12345, "kakao_account": {"email": "user@example.com", "profile": {"nickname": "홍길동"}}}
                """);
        given(userService.getOrCreateUser(SocialProvider.KAKAO, "12345", "user@example.com", "홍길동"))
                .willReturn(new UserLookupResult(userWithId(), false));

        // when
        CustomOAuth2User customUser = (CustomOAuth2User) customOAuth2UserService.loadUser(userRequest("kakao", "id"));

        // then
        assertThat(customUser.isNewUser()).isFalse();
    }

    @Test
    @DisplayName("제공자 응답에 사용자 식별자가 없으면 가입하지 않고 소셜 로그인 실패 코드로 실패한다.")
    void loadUser_withoutSocialId_thenFailWithLoginFailedCode() {
        // given
        respondUserInfo("""
                {"resultcode": "00", "message": "success", "response": {"email": "user@example.com"}}
                """);

        // when & then
        assertThatThrownBy(() -> customOAuth2UserService.loadUser(userRequest("naver", "response")))
                .isInstanceOfSatisfying(OAuth2AuthenticationException.class, e -> {
                    assertThat(e.getError().getErrorCode()).isEqualTo(AuthResponseCode.OAUTH2_LOGIN_FAILED.getCode());
                    assertThat(e.getCause()).isInstanceOf(BaseException.class);
                });
        then(userService).should(never()).getOrCreateUser(any(), any(), any(), any());
    }

    @Test
    @DisplayName("지원하지 않는 제공자면 지원하지 않는 제공자 코드로 실패한다.")
    void loadUser_withUnsupportedProvider_thenFailWithUnsupportedCode() {
        // given
        respondUserInfo("""
                {"sub": "apple-user"}
                """);

        // when & then
        assertThatThrownBy(() -> customOAuth2UserService.loadUser(userRequest("apple", "sub")))
                .isInstanceOfSatisfying(OAuth2AuthenticationException.class, e ->
                        assertThat(e.getError().getErrorCode())
                                .isEqualTo(AuthResponseCode.UNSUPPORTED_SOCIAL_PROVIDER.getCode()));
        then(userService).should(never()).getOrCreateUser(any(), any(), any(), any());
    }

    private void respondUserInfo(String json) {
        providerServer.expect(requestTo(USER_INFO_URI))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer " + ACCESS_TOKEN))
                .andRespond(withSuccess(json, MediaType.APPLICATION_JSON));
    }

    private OAuth2UserRequest userRequest(String registrationId, String userNameAttribute) {
        ClientRegistration registration = ClientRegistration.withRegistrationId(registrationId)
                .clientId("client-id")
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .redirectUri("http://localhost:8080/login/oauth2/code/" + registrationId)
                .authorizationUri("https://provider.example.com/oauth/authorize")
                .tokenUri("https://provider.example.com/oauth/token")
                .userInfoUri(USER_INFO_URI)
                .userNameAttributeName(userNameAttribute)
                .build();
        OAuth2AccessToken accessToken = new OAuth2AccessToken(OAuth2AccessToken.TokenType.BEARER, ACCESS_TOKEN,
                Instant.now(), Instant.now().plusSeconds(3600));
        return new OAuth2UserRequest(registration, accessToken);
    }

    private User userWithId() {
        User user = User.socialSignup(SocialProvider.KAKAO, "12345", "user@example.com", "홍길동");
        ReflectionTestUtils.setField(user, "id", USER_ID);
        return user;
    }
}
