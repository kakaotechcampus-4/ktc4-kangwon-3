package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolReviewStatus;

import java.util.List;

// 분야별 결과 카드
public record PublicToolReviewDto(
        @NotNull ToolName toolName,
        @NotNull ToolReviewStatus status,
        String message,
        List<@NotNull @Valid PublicFindingDto> findings
) {

    public PublicToolReviewDto {
        findings = findings == null ? List.of() : findings;
    }
}
