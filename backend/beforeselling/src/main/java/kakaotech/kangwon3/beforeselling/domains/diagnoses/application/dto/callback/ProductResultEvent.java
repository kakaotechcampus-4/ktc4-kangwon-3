package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.UUID;

// 결과 콜백(eventType = product_result). 실행의 마지막에 진단 결과를 함께 보낸다.
public record ProductResultEvent(
        @NotBlank String eventId,
        @NotNull UUID diagnosisId,
        @NotNull UUID productId,
        @NotBlank String runId,
        @Min(1) int sequence,
        @NotNull @Valid PublicAssessmentDto assessment
) implements ProductEvent {
}
