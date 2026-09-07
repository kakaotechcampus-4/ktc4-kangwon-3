package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.inOrder;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class NaverUnlinkClientTest {

    @Mock
    private ExchangeFunction exchangeFunction;

    @Mock
    private ClientRegistrationRepository clientRegistrationRepository;

    @Test
    @DisplayName("refresh_token으로 access_token을 재발급받은 뒤 그 access_token으로 unlink를 요청한다.")
    void unlink_withRefreshToken_thenReissueAccessTokenAndRevoke() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        NaverUnlinkClient client = new NaverUnlinkClient(webClient, clientRegistrationRepository);
        User user = userWithRefreshToken("naver-refresh-token");

        given(clientRegistrationRepository.findByRegistrationId("naver")).willReturn(naverRegistration());
        given(exchangeFunction.exchange(any())).willReturn(
                Mono.just(jsonResponse("{\"access_token\":\"new-access-token\"}")),
                Mono.just(jsonResponse("{}")));

        // when
        client.unlink(user);

        // then
        ArgumentCaptor<ClientRequest> captor = ArgumentCaptor.forClass(ClientRequest.class);
        InOrder inOrder = inOrder(exchangeFunction);
        then(exchangeFunction).should(inOrder, org.mockito.Mockito.times(2)).exchange(captor.capture());

        ClientRequest reissueRequest = captor.getAllValues().get(0);
        assertThat(reissueRequest.url().toString()).contains("grant_type=refresh_token")
                .contains("refresh_token=naver-refresh-token")
                .contains("client_id=naver-client-id")
                .contains("client_secret=naver-client-secret");

        ClientRequest revokeRequest = captor.getAllValues().get(1);
        assertThat(revokeRequest.url().toString()).contains("grant_type=delete")
                .contains("access_token=new-access-token")
                .contains("service_provider=NAVER");
    }

    @Test
    @DisplayName("access_token 재발급에 실패하면 예외를 던진다.")
    void unlink_whenReissueFails_thenThrow() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        NaverUnlinkClient client = new NaverUnlinkClient(webClient, clientRegistrationRepository);
        User user = userWithRefreshToken("naver-refresh-token");

        given(clientRegistrationRepository.findByRegistrationId("naver")).willReturn(naverRegistration());
        given(exchangeFunction.exchange(any()))
                .willReturn(Mono.just(jsonResponse("{\"error\":\"invalid_grant\"}")));

        // when & then
        assertThatThrownBy(() -> client.unlink(user)).isInstanceOf(IllegalStateException.class);
    }

    private ClientResponse jsonResponse(String body) {
        return ClientResponse.create(HttpStatus.OK)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .body(body)
                .build();
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
