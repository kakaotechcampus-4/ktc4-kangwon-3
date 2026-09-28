package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.config.properties.MailProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.ses.SesClient;
import software.amazon.awssdk.services.ses.model.SendEmailRequest;

import java.nio.charset.StandardCharsets;

@Slf4j
@Component
@RequiredArgsConstructor
@ConditionalOnProperty(prefix = "app.mail", name = "type", havingValue = "SES_API")
public class SesApiMailSender implements MailSender {

    private static final String CHARSET = StandardCharsets.UTF_8.name();

    private final SesClient sesClient;
    private final MailProperties mailProperties;

    @Override
    public void send(MailMessage message) {
        try {
            sesClient.sendEmail(SendEmailRequest.builder()
                    .source("%s <%s>".formatted(mailProperties.fromName(), mailProperties.from()))
                    .destination(destination -> destination.toAddresses(message.to()))
                    .message(mail -> mail
                            .subject(subject -> subject.data(message.subject()).charset(CHARSET))
                            .body(body -> body.html(html -> html.data(message.htmlBody()).charset(CHARSET))))
                    .build());

            log.debug("메일 발송 완료. to={}, subject={}", message.to(), message.subject());
        } catch (Exception e) {
            // 호출부(비동기 리스너)가 재시도 여부를 판단할 수 있도록 삼키지 않고 올린다.
            throw new MailSendFailedException(message.to(), e);
        }
    }
}