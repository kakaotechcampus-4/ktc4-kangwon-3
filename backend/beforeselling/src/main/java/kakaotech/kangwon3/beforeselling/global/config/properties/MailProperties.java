package kakaotech.kangwon3.beforeselling.global.config.properties;

import kakaotech.kangwon3.beforeselling.global.infra.mail.MailSenderType;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties(prefix = "app.mail")
public record MailProperties(
        String from,
        String fromName,
        String region,
        @DefaultValue("NONE") MailSenderType type
) {
}
