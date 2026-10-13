package kakaotech.kangwon3.beforeselling.global.config.properties;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import static org.apache.naming.SelectorContext.prefix;

@Validated
@ConfigurationProperties(prefix = "internal-api")
public record InternalApiProperties(
        @NotBlank @Size(min = 32) String token
) {
}
