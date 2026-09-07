package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.global.config.properties.SocialUnlinkProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;

@Component
@RequiredArgsConstructor
public class KakaoUnlinkClient implements SocialUnlinkClient {

    private static final String UNLINK_URI = "https://kapi.kakao.com/v1/user/unlink";

    private final WebClient webClient;
    private final SocialUnlinkProperties socialUnlinkProperties;

    @Override
    public SocialProvider provider() {
        return SocialProvider.KAKAO;
    }

    @Override
    public void unlink(User user) {
        webClient.post()
                .uri(UNLINK_URI)
                .header(HttpHeaders.AUTHORIZATION, "KakaoAK " + socialUnlinkProperties.kakao().adminKey())
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData("target_id_type", "user_id")
                        .with("target_id", user.getSocialId()))
                .retrieve()
                .toBodilessEntity()
                .block();
    }
}
