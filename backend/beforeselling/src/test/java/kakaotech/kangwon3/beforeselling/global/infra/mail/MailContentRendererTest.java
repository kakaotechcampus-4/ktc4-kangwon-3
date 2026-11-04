package kakaotech.kangwon3.beforeselling.global.infra.mail;

import kakaotech.kangwon3.beforeselling.global.config.MailTemplateConfig;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.thymeleaf.autoconfigure.ThymeleafAutoConfiguration;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 실제 메일 템플릿(templates/mail/*.html, templates/mail/text/*.txt)을 운영과 같은 리졸버 구성으로 렌더링한다.
 */
@Tag("integration")
@SpringJUnitConfig({MailTemplateConfig.class, MailContentRenderer.class})
@ImportAutoConfiguration(ThymeleafAutoConfiguration.class)
class MailContentRendererTest {

    private static final Map<String, Object> VARIABLES = Map.of(
            "amendedOn", "2026-09-29",
            "lawName", "어린이제품 안전 특별법 시행규칙 별표2",
            "summary", "완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다.",
            "affectedProductCount", 2,
            "myPageUrl", "https://palgijeone.com/mypage");

    @Autowired
    private MailContentRenderer mailContentRenderer;

    @Test
    @DisplayName("HTML 템플릿에 변수 값을 채워 렌더링한다.")
    void renderHtml_thenFillVariables() {
        // when
        String html = mailContentRenderer.renderHtml(MailTemplate.LAW_AMENDMENT, VARIABLES);

        // then
        assertThat(html)
                .contains("<html")
                .contains("2026-09-29")
                .contains("어린이제품 안전 특별법 시행규칙 별표2")
                .contains("완구 세부 기준 중 배터리 관련 표시 항목이 조정되었습니다.")
                .contains("https://palgijeone.com/mypage");
    }

    @Test
    @DisplayName("텍스트 템플릿은 .txt 파일을 TEXT 모드로 읽어 변수 값을 채운다.")
    void renderText_thenFillVariablesWithoutHtml() {
        // when
        String text = mailContentRenderer.renderText(MailTemplate.LAW_AMENDMENT, VARIABLES);

        // then
        assertThat(text)
                .contains("개정일 2026-09-29")
                .contains("재확인이 필요한 상품이 2개 있습니다.")
                .contains("https://palgijeone.com/mypage")
                .doesNotContain("<html")
                .doesNotContain("[(${");
    }
}
