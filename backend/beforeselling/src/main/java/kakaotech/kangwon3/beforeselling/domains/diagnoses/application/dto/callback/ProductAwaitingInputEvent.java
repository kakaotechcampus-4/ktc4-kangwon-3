package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.UUID;

// 질문 콜백(eventType = product_awaiting_input)
public record ProductAwaitingInputEvent(
        @NotBlank String eventId,
        @JsonProperty("diagnosisId") @NotNull UUID diagnosesId,
        @NotNull UUID productId,
        @NotBlank String runId,
        @Min(1) int sequence,
        @Min(1) @Max(2) int questionRound,
        @NotEmpty List<@Valid PublicQuestionDto> questions
) implements ProductEvent {
}
