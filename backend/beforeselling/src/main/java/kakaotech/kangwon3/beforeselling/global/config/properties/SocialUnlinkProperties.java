package kakaotech.kangwon3.beforeselling.global.config.properties;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "oauth2.unlink")
public record SocialUnlinkProperties(
        Kakao kakao
) {

    public record Kakao(
            String adminKey
    ) {
    }
}
