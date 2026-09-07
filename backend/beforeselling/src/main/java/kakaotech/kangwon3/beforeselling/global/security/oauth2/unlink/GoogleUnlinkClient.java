package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

@Slf4j
@Component
@RequiredArgsConstructor
public class GoogleUnlinkClient implements SocialUnlinkClient {

    private static final String REVOKE_URI = "https://oauth2.googleapis.com/revoke";

    private final WebClient webClient;

    @Override
    public SocialProvider provider() {
        return SocialProvider.GOOGLE;
    }

    @Override
    public void unlink(User user) {
        String refreshToken = user.getSocialRefreshToken();
        if (refreshToken == null) {
            log.warn("구글 refresh_token이 없어 unlink를 건너뜁니다. userId={}", user.getId());
            return;
        }

        webClient.post()
                .uri(REVOKE_URI)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData("token", refreshToken))
                .retrieve()
                .toBodilessEntity()
                .block();
    }
}
