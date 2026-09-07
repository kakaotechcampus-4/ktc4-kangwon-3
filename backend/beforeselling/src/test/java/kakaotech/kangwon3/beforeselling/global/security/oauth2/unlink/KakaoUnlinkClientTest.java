package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.global.config.properties.SocialUnlinkProperties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class KakaoUnlinkClientTest {

    @Mock
    private ExchangeFunction exchangeFunction;

    @Test
    @DisplayName("Admin Key와 socialId로 카카오 unlink API를 호출한다.")
    void unlink_thenCallKakaoUnlinkApiWithAdminKeyAndSocialId() {
        // given
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        SocialUnlinkProperties properties = new SocialUnlinkProperties(new SocialUnlinkProperties.Kakao("admin-key-value"));
        KakaoUnlinkClient client = new KakaoUnlinkClient(webClient, properties);
        User user = User.socialSignup(SocialProvider.KAKAO, "kakao-social-id", "user@example.com", "사용자");

        given(exchangeFunction.exchange(any()))
                .willReturn(Mono.just(ClientResponse.create(HttpStatus.OK).build()));

        // when
        client.unlink(user);

        // then
        ArgumentCaptor<ClientRequest> captor = ArgumentCaptor.forClass(ClientRequest.class);
        then(exchangeFunction).should().exchange(captor.capture());

        ClientRequest request = captor.getValue();
        assertThat(request.method()).isEqualTo(HttpMethod.POST);
        assertThat(request.url().toString()).isEqualTo("https://kapi.kakao.com/v1/user/unlink");
        assertThat(request.headers().getFirst(HttpHeaders.AUTHORIZATION)).isEqualTo("KakaoAK admin-key-value");
        assertThat(WebClientRequestBodyReader.readBodyAsString(request))
                .isEqualTo("target_id_type=user_id&target_id=kakao-social-id");
    }

    @Test
    @DisplayName("KAKAO provider를 반환한다.")
    void provider_thenReturnKakao() {
        WebClient webClient = WebClient.builder().exchangeFunction(exchangeFunction).build();
        KakaoUnlinkClient client = new KakaoUnlinkClient(webClient,
                new SocialUnlinkProperties(new SocialUnlinkProperties.Kakao("admin-key-value")));

        assertThat(client.provider()).isEqualTo(SocialProvider.KAKAO);
    }
}
