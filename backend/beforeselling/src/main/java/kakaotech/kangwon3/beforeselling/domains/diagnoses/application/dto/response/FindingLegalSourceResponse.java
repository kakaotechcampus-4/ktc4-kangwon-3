package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import java.util.UUID;

// 판단 항목의 법령·기관 근거
public record FindingLegalSourceResponse(
        UUID findingLegalSourceId,
        String sourceName,
        String lawName,
        String article,
        String quotedText,
        String sourceUrl,
        String effectiveDate
) {
}
