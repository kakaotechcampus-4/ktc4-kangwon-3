package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.config.properties.MailProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.ses.SesClient;
import software.amazon.awssdk.services.ses.model.SendEmailRequest;
import software.amazon.awssdk.services.ses.model.SesException;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class SesApiMailSenderTest {

    private static final MailMessage MESSAGE = new MailMessage(
            "user@example.com", "[팔기전에] 관련 법령이 개정되었습니다", "<p>html</p>", "text");

    @Mock
    private SesClient sesClient;

    private SesApiMailSender mailSender;

    @BeforeEach
    void setUp() {
        mailSender = new SesApiMailSender(sesClient,
                new MailProperties("noreply@palgijeone.com", "팔기전에", "ap-northeast-2", MailSenderType.SES_API));
    }

    @Test
    @DisplayName("SES 요청에 수신자·제목·HTML·텍스트 본문을 UTF-8로 담고, 한글 발신자 이름은 RFC 2047로 인코딩한다.")
    void send_thenBuildSesRequest() {
        // given
        ArgumentCaptor<SendEmailRequest> captor = ArgumentCaptor.forClass(SendEmailRequest.class);

        // when
        mailSender.send(MESSAGE);

        // then
        then(sesClient).should().sendEmail(captor.capture());
        SendEmailRequest request = captor.getValue();
        String encodedName = Base64.getEncoder().encodeToString("팔기전에".getBytes(StandardCharsets.UTF_8));
        assertThat(request.source()).isEqualTo("=?UTF-8?B?" + encodedName + "?= <noreply@palgijeone.com>");
        assertThat(request.destination().toAddresses()).containsExactly("user@example.com");
        assertThat(request.message().subject().data()).isEqualTo(MESSAGE.subject());
        assertThat(request.message().subject().charset()).isEqualTo("UTF-8");
        assertThat(request.message().body().html().data()).isEqualTo("<p>html</p>");
        assertThat(request.message().body().text().data()).isEqualTo("text");
    }

    @Test
    @DisplayName("SES 호출이 실패하면 수신자를 담은 MailSendFailedException으로 감싸 던진다.")
    void send_whenSesFails_thenThrowMailSendFailed() {
        // given
        SesException cause = (SesException) SesException.builder().message("throttled").build();
        given(sesClient.sendEmail(any(SendEmailRequest.class))).willThrow(cause);

        // when & then
        assertThatThrownBy(() -> mailSender.send(MESSAGE))
                .isInstanceOf(MailSendFailedException.class)
                .hasMessageContaining("user@example.com")
                .hasCause(cause);
    }

    @Test
    @DisplayName("닫으면 SES 클라이언트도 닫는다.")
    void close_thenCloseSesClient() {
        // when
        mailSender.close();

        // then
        then(sesClient).should().close();
    }
}
