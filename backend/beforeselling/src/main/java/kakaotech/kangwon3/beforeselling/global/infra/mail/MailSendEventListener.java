package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.infra.mail.event.MailSendRequestedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.util.StringUtils;

@Slf4j
@Component
@RequiredArgsConstructor
public class MailSendEventListener {

    private final MailContentRenderer mailContentRenderer;
    private final MailSender mailSender;

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(MailSendRequestedEvent event) {
        // 소셜 로그인에서 이메일 제공에 동의하지 않은 사용자는 이메일이 없다.
        if (!StringUtils.hasText(event.to())) {
            log.debug("수신 이메일이 없어 발송을 건너뜁니다. template={}", event.template());
            return;
        }

        MailTemplate template = event.template();
        try {
            mailSender.send(new MailMessage(
                    event.to(),
                    template.getSubject(),
                    mailContentRenderer.renderHtml(template, event.variables()),
                    mailContentRenderer.renderText(template, event.variables())));
        } catch (Exception e) {
            // 재시도는 아직 두지 않는다.
            log.error("메일 발송 실패. template={}", template, e);
        }
    }

}
