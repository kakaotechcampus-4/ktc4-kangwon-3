package kakaotech.kangwon3.beforeselling.global.infra.mail;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@ConditionalOnProperty(prefix = "app.mail", name = "type", havingValue = "NONE", matchIfMissing = true)
public class LoggingMailSender implements MailSender {

    @Override
    public void send(MailMessage message) {
        log.info("""
                [메일 발송 생략 — app.mail.type=NONE]
                  to      : {}
                  subject : {}
                  text    :
                {}""", message.to(), message.subject(), message.textBody());
    }
}
