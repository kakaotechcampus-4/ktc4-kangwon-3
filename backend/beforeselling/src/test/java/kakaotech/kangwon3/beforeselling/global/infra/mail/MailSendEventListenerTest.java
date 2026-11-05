package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.infra.mail.event.MailSendRequestedEvent;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class MailSendEventListenerTest {

    private static final Map<String, Object> VARIABLES = Map.of("lawName", "어린이제품 안전 특별법");

    @Mock
    private MailContentRenderer mailContentRenderer;

    @Mock
    private MailSender mailSender;

    @InjectMocks
    private MailSendEventListener listener;

    @Test
    @DisplayName("발송 요청을 받으면 템플릿 제목과 렌더링한 HTML·텍스트 본문으로 메일을 보낸다.")
    void handle_thenSendRenderedMail() {
        // given
        given(mailContentRenderer.renderHtml(MailTemplate.LAW_AMENDMENT, VARIABLES)).willReturn("<p>html</p>");
        given(mailContentRenderer.renderText(MailTemplate.LAW_AMENDMENT, VARIABLES)).willReturn("text");

        // when
        listener.handle(new MailSendRequestedEvent("user@example.com", MailTemplate.LAW_AMENDMENT, VARIABLES));

        // then
        then(mailSender).should().send(new MailMessage(
                "user@example.com", MailTemplate.LAW_AMENDMENT.getSubject(), "<p>html</p>", "text"));
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   "})
    @DisplayName("수신 이메일이 없으면 렌더링·발송 없이 건너뛴다.")
    void handle_withoutEmail_thenSkip(String to) {
        // when
        listener.handle(new MailSendRequestedEvent(to, MailTemplate.LAW_AMENDMENT, VARIABLES));

        // then
        then(mailContentRenderer).shouldHaveNoInteractions();
        then(mailSender).should(never()).send(any());
    }

    @Test
    @DisplayName("발송에 실패해도 예외를 밖으로 던지지 않는다.")
    void handle_whenSendFails_thenSwallowException() {
        // given
        given(mailContentRenderer.renderHtml(MailTemplate.LAW_AMENDMENT, VARIABLES)).willReturn("<p>html</p>");
        given(mailContentRenderer.renderText(MailTemplate.LAW_AMENDMENT, VARIABLES)).willReturn("text");
        willThrow(new MailSendFailedException("user@example.com", new RuntimeException("ses down")))
                .given(mailSender).send(any());

        // when & then
        assertThatCode(() -> listener.handle(
                new MailSendRequestedEvent("user@example.com", MailTemplate.LAW_AMENDMENT, VARIABLES)))
                .doesNotThrowAnyException();
    }
}
