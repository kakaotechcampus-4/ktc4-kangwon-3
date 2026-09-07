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
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class GoogleUnlinkClientTest {

    @Mock
    private ExchangeFunction exchangeFunction;

    @Test
    @DisplayName("저장된 refresh_token으로 구글 revoke API를 호출한다.")
    void unlink_withRefreshToken_thenCallGoogleRevokeApi() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        GoogleUnlinkClient client = new GoogleUnlinkClient(webClient);
        User user = userWithRefreshToken("google-refresh-token");

        given(exchangeFunction.exchange(any()))
                .willReturn(Mono.just(ClientResponse.create(HttpStatus.OK).build()));

        // when
        client.unlink(user);

        // then
        ArgumentCaptor<ClientRequest> captor = ArgumentCaptor.forClass(ClientRequest.class);
        then(exchangeFunction).should().exchange(captor.capture());

        ClientRequest request = captor.getValue();
        assertThat(request.method()).isEqualTo(HttpMethod.POST);
        assertThat(request.url().toString()).isEqualTo("https://oauth2.googleapis.com/revoke");
        assertThat(WebClientRequestBodyReader.readBodyAsString(request)).isEqualTo("token=google-refresh-token");
    }

    @Test
    @DisplayName("refresh_token이 없으면 API를 호출하지 않고 건너뛴다.")
    void unlink_withoutRefreshToken_thenSkip() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        GoogleUnlinkClient client = new GoogleUnlinkClient(webClient);
        User user = User.socialSignup(SocialProvider.GOOGLE, "google-social-id", "user@example.com", "사용자");

        // when
        client.unlink(user);

        // then
        then(exchangeFunction).should(never()).exchange(any());
    }

    private User userWithRefreshToken(String refreshToken) {
        User user = User.socialSignup(SocialProvider.GOOGLE, "google-social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "socialRefreshToken", refreshToken);
        return user;
    }
}
