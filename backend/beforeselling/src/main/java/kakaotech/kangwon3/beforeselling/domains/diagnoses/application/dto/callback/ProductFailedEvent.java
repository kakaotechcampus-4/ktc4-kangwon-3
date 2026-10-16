package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;

import java.util.UUID;

// 실패 콜백(eventType = product_failed)
public record ProductFailedEvent(
        @NotBlank String eventId,
        @NotNull UUID diagnosisId,
        @NotNull UUID productId,
        @NotBlank String runId,
        @Min(1) int sequence,
        PipelineStage stage,
        @NotNull @Valid PublicErrorDto error
) implements ProductEvent {
}
