package kakaotech.kangwon3.beforeselling.global.infra.mail;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.thymeleaf.TemplateEngine;
import org.thymeleaf.context.Context;

import java.util.Map;

@Component
@RequiredArgsConstructor
public class MailContentRenderer {

    private static final String HTML_PREFIX = "mail/";
    private static final String TEXT_PREFIX = "mail/text/";

    private final TemplateEngine templateEngine;

    public String renderHtml(MailTemplate template, Map<String, Object> variables) {
        return render(HTML_PREFIX + template.getFileName(), variables);
    }

    public String renderText(MailTemplate template, Map<String, Object> variables) {
        return render(TEXT_PREFIX + template.getFileName(), variables);
    }

    private String render(String templateName, Map<String, Object> variables) {
        Context context = new Context();
        context.setVariables(variables);

        return templateEngine.process(templateName, context);
    }
}
