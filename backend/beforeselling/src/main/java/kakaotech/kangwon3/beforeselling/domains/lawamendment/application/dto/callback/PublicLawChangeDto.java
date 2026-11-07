package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;

import java.time.LocalDate;

// 근거 문서 변경 하나. 길이 제한은 LawAmendment 컬럼 길이와 같다.
public record PublicLawChangeDto(
        @NotBlank @Size(max = 255) String lawName,
        @NotBlank @Size(max = 50) String documentId,
        @NotNull Boolean admrul,
        @NotNull ToolName toolName,
        @NotBlank @Size(max = 50) String serialNumber,
        @Size(max = 50) String previousSerialNumber,
        @Size(max = 50) String revisionType,
        LocalDate enforceDate,
        LocalDate issuedDate
) {
}
