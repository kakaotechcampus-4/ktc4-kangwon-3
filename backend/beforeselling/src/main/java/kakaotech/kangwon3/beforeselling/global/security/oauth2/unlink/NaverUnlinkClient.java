package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

@Slf4j
@Component
@RequiredArgsConstructor
public class NaverUnlinkClient implements SocialUnlinkClient {

    private static final String REGISTRATION_ID = "naver";
    private static final String REVOKE_URI = "https://nid.naver.com/oauth2.0/revoke";

    private final RestClient restClient;
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

        MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
        body.add("client_id", registration.getClientId());
        body.add("client_secret", registration.getClientSecret());
        body.add("token", refreshToken);
        body.add("token_type_hint", "refresh_token");

        restClient.post()
                .uri(REVOKE_URI)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(body)
                .retrieve()
                .toBodilessEntity();
    }
}
