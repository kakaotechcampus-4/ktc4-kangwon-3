package kakaotech.kangwon3.beforeselling.global.config.properties;

import kakaotech.kangwon3.beforeselling.global.infra.mail.MailSenderType;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.mail")
public record MailProperties(
        String from,
        String fromName,
        String region,
        MailSenderType type
) {
}
