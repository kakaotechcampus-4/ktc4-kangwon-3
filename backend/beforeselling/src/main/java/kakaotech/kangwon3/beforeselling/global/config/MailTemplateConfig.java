package kakaotech.kangwon3.beforeselling.global.config;

import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.thymeleaf.spring6.templateresolver.SpringResourceTemplateResolver;
import org.thymeleaf.templatemode.TemplateMode;

import java.util.Set;

/**
 * 메일 평문(text/plain) 본문용 템플릿 리졸버.
 *
 * Spring Boot 가 자동 등록하는 리졸버는 .html + HTML 모드 하나뿐이라 .txt 를 읽지 못한다.
 * TEXT 모드 리졸버를 하나 더 두되, resolvablePatterns 로 mail/text/* 만 맡게 해서
 * 나머지 템플릿은 기존 리졸버가 그대로 처리하게 한다.
 */
@Configuration
public class MailTemplateConfig {

    @Bean
    public SpringResourceTemplateResolver mailTextTemplateResolver(ApplicationContext applicationContext) {
        SpringResourceTemplateResolver resolver = new SpringResourceTemplateResolver();

        resolver.setApplicationContext(applicationContext);
        resolver.setPrefix("classpath:/templates/");
        resolver.setSuffix(".txt");
        resolver.setTemplateMode(TemplateMode.TEXT);
        resolver.setCharacterEncoding("UTF-8");
        resolver.setResolvablePatterns(Set.of("mail/text/*"));
        // 기본 리졸버보다 먼저 확인하게 한다. 패턴이 안 맞으면 다음 리졸버로 넘어간다.
        resolver.setOrder(0);

        return resolver;
    }
}
