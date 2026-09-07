package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink.dto.NaverTokenResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

@Slf4j
@Component
@RequiredArgsConstructor
public class NaverUnlinkClient implements SocialUnlinkClient {

    private static final String REGISTRATION_ID = "naver";

    private final WebClient webClient;
    private final ClientRegistrationRepository clientRegistrationRepository;

    @Override
    public SocialProvider provider() {
        return SocialProvider.NAVER;
    }

    @Override
    public void unlink(User user) {
        String refreshToken = user.getSocialRefreshToken();
        if (refreshToken == null) {
            log.warn("네이버 refresh_token이 없어 unlink를 건너뜁니다. userId={}", user.getId());
            return;
        }

        ClientRegistration registration = clientRegistrationRepository.findByRegistrationId(REGISTRATION_ID);
        String accessToken = reissueAccessToken(registration, refreshToken);
        revoke(registration, accessToken);
    }

    private String reissueAccessToken(ClientRegistration registration, String refreshToken) {
        NaverTokenResponse response = webClient.post()
                .uri(uriBuilder -> uriBuilder.scheme("https").host("nid.naver.com").path("/oauth2.0/token")
                        .queryParam("grant_type", "refresh_token")
                        .queryParam("client_id", registration.getClientId())
                        .queryParam("client_secret", registration.getClientSecret())
                        .queryParam("refresh_token", refreshToken)
                        .build())
                .retrieve()
                .bodyToMono(NaverTokenResponse.class)
                .block();

        if (response == null || response.accessToken() == null) {
            throw new IllegalStateException("네이버 access_token 재발급에 실패했습니다: "
                    + (response == null ? "empty response" : response.error()));
        }
        return response.accessToken();
    }

    private void revoke(ClientRegistration registration, String accessToken) {
        NaverTokenResponse response = webClient.post()
                .uri(uriBuilder -> uriBuilder.scheme("https").host("nid.naver.com").path("/oauth2.0/token")
                        .queryParam("grant_type", "delete")
                        .queryParam("client_id", registration.getClientId())
                        .queryParam("client_secret", registration.getClientSecret())
                        .queryParam("access_token", accessToken)
                        .queryParam("service_provider", "NAVER")
                        .build())
                .retrieve()
                .bodyToMono(NaverTokenResponse.class)
                .block();

        if (response != null && response.error() != null) {
            throw new IllegalStateException("네이버 unlink에 실패했습니다: " + response.error());
        }
    }
}
