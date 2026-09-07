package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class NaverUnlinkClientTest {

    @Mock
    private ExchangeFunction exchangeFunction;

    @Mock
    private ClientRegistrationRepository clientRegistrationRepository;

    @Test
    @DisplayName("저장된 refresh_token으로 네이버 Token Revocation API(token_type_hint=refresh_token)를 호출한다.")
    void unlink_withRefreshToken_thenCallNaverRevokeApi() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        NaverUnlinkClient client = new NaverUnlinkClient(webClient, clientRegistrationRepository);
        User user = userWithRefreshToken("naver-refresh-token");

        given(clientRegistrationRepository.findByRegistrationId("naver")).willReturn(naverRegistration());
        given(exchangeFunction.exchange(any()))
                .willReturn(Mono.just(ClientResponse.create(HttpStatus.OK).build()));

        // when
        client.unlink(user);

        // then
        ArgumentCaptor<ClientRequest> captor = ArgumentCaptor.forClass(ClientRequest.class);
        then(exchangeFunction).should().exchange(captor.capture());

        ClientRequest request = captor.getValue();
        assertThat(request.method()).isEqualTo(HttpMethod.POST);
        assertThat(request.url().toString()).isEqualTo("https://nid.naver.com/oauth2.0/revoke");
        assertThat(WebClientRequestBodyReader.readBodyAsString(request)).isEqualTo(
                "client_id=naver-client-id&client_secret=naver-client-secret"
                        + "&token=naver-refresh-token&token_type_hint=refresh_token");
    }

    @Test
    @DisplayName("refresh_token이 없으면 API를 호출하지 않고 건너뛴다.")
    void unlink_withoutRefreshToken_thenSkip() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        NaverUnlinkClient client = new NaverUnlinkClient(webClient, clientRegistrationRepository);
        User user = User.socialSignup(SocialProvider.NAVER, "naver-social-id", "user@example.com", "사용자");

        // when
        client.unlink(user);

        // then
        then(exchangeFunction).should(never()).exchange(any());
    }

    @Test
    @DisplayName("네이버가 실패 상태 코드를 응답하면 예외를 던진다(성공 판단은 응답 바디가 아닌 상태 코드 기준).")
    void unlink_whenNaverRespondsWithErrorStatus_thenThrow() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        NaverUnlinkClient client = new NaverUnlinkClient(webClient, clientRegistrationRepository);
        User user = userWithRefreshToken("naver-refresh-token");

        given(clientRegistrationRepository.findByRegistrationId("naver")).willReturn(naverRegistration());
        given(exchangeFunction.exchange(any())).willReturn(Mono.just(
                ClientResponse.create(HttpStatus.UNAUTHORIZED)
                        .body("{\"error\":\"unauthorized_client\",\"error_description\":\"Client authentication failed.\"}")
                        .build()));

        // when & then
        assertThatThrownBy(() -> client.unlink(user)).isInstanceOf(WebClientResponseException.class);
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
