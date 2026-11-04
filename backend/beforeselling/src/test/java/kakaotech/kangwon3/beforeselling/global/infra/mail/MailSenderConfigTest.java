package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.config.properties.MailProperties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

class MailSenderConfigTest {

    @Test
    @DisplayName("메일 타입이 NONE이면 실제로 보내지 않고 로그만 남기는 구현을 쓴다.")
    void mailSender_withNone_thenLoggingMailSender() {
        // when
        MailSender mailSender = mailSenderOf(MailSenderType.NONE);

        // then
        assertThat(mailSender).isInstanceOf(LoggingMailSender.class);
        assertThatCode(() -> mailSender.send(new MailMessage("user@example.com", "제목", "<p>html</p>", "text")))
                .doesNotThrowAnyException();
    }

    @Test
    @DisplayName("메일 타입이 비어 있으면(null) NONE으로 취급한다.")
    void mailSender_withNullType_thenLoggingMailSender() {
        // when & then
        assertThat(mailSenderOf(null)).isInstanceOf(LoggingMailSender.class);
    }

    @Test
    @DisplayName("메일 타입이 SES_API면 SES 발송 구현을 쓴다.")
    void mailSender_withSesApi_thenSesApiMailSender() {
        // when
        MailSender mailSender = mailSenderOf(MailSenderType.SES_API);

        // then
        assertThat(mailSender).isInstanceOf(SesApiMailSender.class);
        ((SesApiMailSender) mailSender).close();
    }

    private MailSender mailSenderOf(MailSenderType type) {
        return new MailSenderConfig(new MailProperties("noreply@palgijeone.com", "팔기전에", "ap-northeast-2", type))
                .mailSender();
    }
}
