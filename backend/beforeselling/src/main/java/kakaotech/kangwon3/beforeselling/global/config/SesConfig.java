package kakaotech.kangwon3.beforeselling.global.config;

import kakaotech.kangwon3.beforeselling.global.config.properties.MailProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.ses.SesClient;

@Configuration
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "app.mail", name = "type", havingValue = "SES_API")
public class SesConfig {

    private final MailProperties mailProperties;

    @Bean
    public SesClient sesClient() {
        return SesClient.builder()
                .region(Region.of(mailProperties.region()))
                .credentialsProvider(DefaultCredentialsProvider.builder().build())
                .build();
    }
}
