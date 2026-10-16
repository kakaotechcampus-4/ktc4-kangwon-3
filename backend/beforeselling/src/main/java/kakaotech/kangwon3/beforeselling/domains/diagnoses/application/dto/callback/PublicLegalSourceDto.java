package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

// 판단 항목의 법령·기관 근거. 길이 제한은 FindingLegalSource 컬럼 길이와 같다.
public record PublicLegalSourceDto(
        @NotBlank @Size(max = 255) String sourceName,
        @Size(max = 255) String lawName,
        @Size(max = 255) String article,
        String quotedText,
        String sourceUrl,
        // AI가 형식 보장 없이 문자열로 준다(예: "2026-01-01").
        @Size(max = 50) String effectiveDate
) {
}
