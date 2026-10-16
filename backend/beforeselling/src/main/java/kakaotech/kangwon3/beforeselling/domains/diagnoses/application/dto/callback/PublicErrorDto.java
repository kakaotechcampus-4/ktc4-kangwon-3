package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record PublicErrorDto(
        // AI_PIPELINE_ERROR, AI_TIMEOUT 등. Product.errorCode 컬럼 길이와 같다.
        @NotBlank @Size(max = 50) String code,
        @NotBlank String message,
        Boolean retryable
) {
}
