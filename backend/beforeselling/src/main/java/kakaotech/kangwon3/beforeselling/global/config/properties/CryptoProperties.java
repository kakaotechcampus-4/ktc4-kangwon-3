package kakaotech.kangwon3.beforeselling.global.config.properties;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "crypto")
public record CryptoProperties(
        String secretKey
) {
}
