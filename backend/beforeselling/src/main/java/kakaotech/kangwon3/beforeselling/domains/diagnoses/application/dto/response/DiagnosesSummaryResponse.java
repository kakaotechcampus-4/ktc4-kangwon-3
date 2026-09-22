package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;

import java.time.LocalDateTime;

public record DiagnosesSummaryResponse(
        Long diagnosesId,
        ProcessingStatus processingStatus,
        int productCount,
        String representativeProductName,
        String representativeProductImageUrl,
        LocalDateTime createdAt
) {
}