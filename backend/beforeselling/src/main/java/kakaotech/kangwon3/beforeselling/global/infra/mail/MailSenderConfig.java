package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.config.properties.MailProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.ses.SesClient;

import java.util.Objects;

@Configuration
@RequiredArgsConstructor
public class MailSenderConfig {

    private final MailProperties mailProperties;

    @Bean
    public MailSender mailSender() {
        // MAIL_TYPE="" 처럼 빈 값이면 enum 바인딩 결과가 null 이 되므로 NONE 으로 취급한다.
        MailSenderType type = Objects.requireNonNullElse(mailProperties.type(), MailSenderType.NONE);

        return switch (type) {
            case NONE -> new LoggingMailSender();
            case SES_API -> new SesApiMailSender(createSesClient(), mailProperties);
        };
    }

    private SesClient createSesClient() {
        return SesClient.builder()
                .region(Region.of(mailProperties.region()))
                .credentialsProvider(DefaultCredentialsProvider.builder().build())
                .build();
    }
}
