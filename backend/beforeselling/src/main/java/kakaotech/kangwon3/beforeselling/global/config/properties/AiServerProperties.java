package kakaotech.kangwon3.beforeselling.global.config.properties;

import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

// BE → AI 진단 요청 대상 AI 서버 주소 (예: http://ai-server:8000)
@Validated
@ConfigurationProperties(prefix = "ai-server")
public record AiServerProperties(
        @NotBlank String baseUrl
) {
}
