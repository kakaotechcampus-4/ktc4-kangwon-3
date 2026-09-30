package kakaotech.kangwon3.beforeselling.global.infra.mail;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.util.Map;

/**
 * 실제 SES 로 메일을 보내 보는 수동 확인용 테스트.
 * MAIL_TEST_TO 가 없으면 건너뛰므로 CI 와 평소 테스트에서는 실행되지 않는다.
 *
 * 실행: aws sso login 후
 *   MAIL_TEST_TO=받을주소 ./gradlew test --tests '*SesMailManualTest'
 */
@SpringBootTest(properties = {
        "app.mail.type=SES_API",
        // application-test.yaml 의 발신 주소(noreply@test.local)는 SES 인증 도메인이 아니라 거부된다.
        "app.mail.from=noreply@palgijeone.com"
})
@ActiveProfiles("test")
@EnabledIfEnvironmentVariable(named = "MAIL_TEST_TO", matches = ".+")
class SesMailManualTest {

    @Autowired
    private MailSender mailSender;

    @Autowired
    private MailContentRenderer mailContentRenderer;

    @Test
    @DisplayName("법령 개정 알림 메일을 실제 SES 로 발송한다.")
    void sendLawAmendmentMail() {
        MailTemplate template = MailTemplate.LAW_AMENDMENT;
        Map<String, Object> variables = Map.of(
                "amendedOn", "2026-09-29",
                "lawName", "어린이제품 안전 특별법 시행규칙 별표2",
                "summary", "[테스트] 완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다.",
                "affectedProductCount", 2,
                "myPageUrl", "https://palgijeone.com/mypage");

        // 리스너(비동기)를 거치지 않고 직접 호출한다. 실패하면 예외가 그대로 올라와 테스트가 실패한다.
        mailSender.send(new MailMessage(
                System.getenv("MAIL_TEST_TO"),
                template.getSubject(),
                mailContentRenderer.renderHtml(template, variables),
                mailContentRenderer.renderText(template, variables)));
    }
}
