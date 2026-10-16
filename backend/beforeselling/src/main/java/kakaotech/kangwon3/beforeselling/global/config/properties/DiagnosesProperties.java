package kakaotech.kangwon3.beforeselling.global.config.properties;

import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

@Validated
@ConfigurationProperties(prefix = "diagnoses")
public record DiagnosesProperties(
        @NotNull Duration stuckThreshold
) {
}
