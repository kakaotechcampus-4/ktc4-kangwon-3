package kakaotech.kangwon3.beforeselling.global.infra.mail.event;

import kakaotech.kangwon3.beforeselling.global.infra.mail.MailTemplate;

import java.util.Map;

/**
 * 메일 한 통의 발송 요청. 본문은 발송 시점에 리스너가 렌더링한다.
 * variables 는 템플릿이 요구하는 변수를 모두 담아야 한다(빠지면 빈칸으로 렌더링된다).
 */
public record MailSendRequestedEvent(
        String to,
        MailTemplate template,
        Map<String, Object> variables
) {
}
