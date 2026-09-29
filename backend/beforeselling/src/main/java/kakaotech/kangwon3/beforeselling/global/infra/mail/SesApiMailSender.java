package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.config.properties.MailProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.ses.SesClient;
import software.amazon.awssdk.services.ses.model.SendEmailRequest;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

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
                    .source(formatSource())
                    .destination(destination -> destination.toAddresses(message.to()))
                    .message(mail -> mail
                            .subject(subject -> subject.data(message.subject()).charset(CHARSET))
                            .body(body -> body
                                    .html(html -> html.data(message.htmlBody()).charset(CHARSET))
                                    .text(text -> text.data(message.textBody()).charset(CHARSET))))
                    .build());

            log.debug("메일 발송 완료. to={}, subject={}", message.to(), message.subject());
        } catch (Exception e) {
            // 호출부(비동기 리스너)가 재시도 여부를 판단할 수 있도록 삼키지 않고 올린다.
            throw new MailSendFailedException(message.to(), e);
        }
    }
    // SES 는 Source 에 ASCII 가 아닌 문자가 있으면 RFC 2047 인코딩을 요구한다.
    private String formatSource() {
        String encodedName = Base64.getEncoder()
                .encodeToString(mailProperties.fromName().getBytes(StandardCharsets.UTF_8));
        return "=?UTF-8?B?%s?= <%s>".formatted(encodedName, mailProperties.from());
    }
}