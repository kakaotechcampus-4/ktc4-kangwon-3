package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// 사용자에게 물을 질문 하나
public record PublicQuestionDto(
        @NotBlank @Size(max = 50) String questionKey,
        @Min(1) int questionOrder,
        @NotBlank String questionText,
        String helpText
) {
}
