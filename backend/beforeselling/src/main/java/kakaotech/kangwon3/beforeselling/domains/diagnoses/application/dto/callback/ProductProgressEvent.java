package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;

import java.util.UUID;

// 진행 콜백(eventType = product_progress)
public record ProductProgressEvent(
        @NotBlank String eventId,
        @JsonProperty("diagnosisId") @NotNull UUID diagnosesId,
        @NotNull UUID productId,
        @NotBlank String runId,
        @Min(1) int sequence,
        @NotNull PipelineStage stage,
        @NotNull StageStatus stageStatus,
        ToolName toolName
) implements ProductEvent {
}
