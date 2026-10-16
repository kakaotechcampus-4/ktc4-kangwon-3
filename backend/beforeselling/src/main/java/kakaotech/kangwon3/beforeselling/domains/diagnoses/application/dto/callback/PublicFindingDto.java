package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;

import java.util.List;

// 결과 카드 안의 판단 항목 하나
public record PublicFindingDto(
        // ProductFinding.subject 컬럼 길이와 같다.
        @NotBlank @Size(max = 255) String subject,
        @NotNull Determination determination,
        @NotNull RiskLevel riskLevel,
        @NotBlank String summary,
        @NotBlank String rationale,
        List<@NotNull @Valid PublicLegalSourceDto> legalSources
) {

    public PublicFindingDto {
        legalSources = legalSources == null ? List.of() : legalSources;
    }
}
