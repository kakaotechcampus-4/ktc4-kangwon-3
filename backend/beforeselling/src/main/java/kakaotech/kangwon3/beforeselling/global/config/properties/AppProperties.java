package kakaotech.kangwon3.beforeselling.global.config.properties;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.List;

@ConfigurationProperties(prefix = "app")
public record AppProperties(
        Cors cors,
        OAuth2 oauth2,
        Cookie cookie
) {

    public record Cors(
            List<String> allowedOrigins
    ) {
    }

    public record OAuth2(
            String frontendRedirectUri
    ) {
    }

    public record Cookie(
            boolean secure,
            String sameSite
    ) {
    }
}
