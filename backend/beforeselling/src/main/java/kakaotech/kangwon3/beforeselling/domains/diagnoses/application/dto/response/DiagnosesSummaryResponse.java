package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;

import java.time.LocalDateTime;
import java.util.UUID;

public record DiagnosesSummaryResponse(
        UUID diagnosesId,
        ProcessingStatus processingStatus,
        int productCount,
        String representativeProductName,
        String representativeProductImageUrl,
        LocalDateTime createdAt
) {
}