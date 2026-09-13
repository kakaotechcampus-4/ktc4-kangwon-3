package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

@ExtendWith(MockitoExtension.class)
class NaverUnlinkClientTest {

    @Mock
    private ClientRegistrationRepository clientRegistrationRepository;

    @Test
    @DisplayName("저장된 refresh_token으로 네이버 Token Revocation API(token_type_hint=refresh_token)를 호출한다.")
    void unlink_withRefreshToken_thenCallNaverRevokeApi() {
        // given
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();

        NaverUnlinkClient client = new NaverUnlinkClient(restClient, clientRegistrationRepository);
        User user = userWithRefreshToken("naver-refresh-token");

        given(clientRegistrationRepository.findByRegistrationId("naver")).willReturn(naverRegistration());
        server.expect(requestTo("https://nid.naver.com/oauth2.0/revoke"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().string(
                        "client_id=naver-client-id&client_secret=naver-client-secret"
                                + "&token=naver-refresh-token&token_type_hint=refresh_token"))
                .andRespond(withSuccess());

        // when
        client.unlink(user);

        // then
        server.verify();
    }

    @Test
    @DisplayName("네이버가 실패 상태 코드를 응답하면 예외를 던진다(성공 판단은 응답 바디가 아닌 상태 코드 기준).")
    void unlink_whenNaverRespondsWithErrorStatus_thenThrow() {
        // given
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();

        NaverUnlinkClient client = new NaverUnlinkClient(restClient, clientRegistrationRepository);
        User user = userWithRefreshToken("naver-refresh-token");

        given(clientRegistrationRepository.findByRegistrationId("naver")).willReturn(naverRegistration());
        server.expect(requestTo("https://nid.naver.com/oauth2.0/revoke"))
                .andRespond(withStatus(HttpStatus.UNAUTHORIZED)
                        .body("{\"error\":\"unauthorized_client\",\"error_description\":\"Client authentication failed.\"}"));

        // when & then
        assertThatThrownBy(() -> client.unlink(user)).isInstanceOf(RestClientResponseException.class);
    }

    private ClientRegistration naverRegistration() {
        return ClientRegistration.withRegistrationId("naver")
                .clientId("naver-client-id")
                .clientSecret("naver-client-secret")
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .redirectUri("{baseUrl}/login/oauth2/code/{registrationId}")
                .authorizationUri("https://nid.naver.com/oauth2.0/authorize")
                .tokenUri("https://nid.naver.com/oauth2.0/token")
                .build();
    }

    private User userWithRefreshToken(String refreshToken) {
        User user = User.socialSignup(SocialProvider.NAVER, "naver-social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "socialRefreshToken", refreshToken);
        return user;
    }
}
