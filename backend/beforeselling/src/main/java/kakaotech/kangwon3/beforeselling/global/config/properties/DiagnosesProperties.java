package kakaotech.kangwon3.beforeselling.global.config.properties;

import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

@Validated
@ConfigurationProperties(prefix = "diagnoses")
public record DiagnosesProperties(
        @NotNull Duration stuckThreshold,

        // FE가 진단서를 다시 조회할 간격
        @NotNull Duration pollInterval,

        // AI가 요청을 받지 않은 상품을 다시 요청하는 기한. 마지막 요청 후 이 시간이 지나면 실패 처리한다.
        @NotNull Duration requestRetryDeadline
) {
}
