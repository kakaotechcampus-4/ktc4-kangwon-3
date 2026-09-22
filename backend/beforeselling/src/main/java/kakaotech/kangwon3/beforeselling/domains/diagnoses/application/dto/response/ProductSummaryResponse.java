package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.time.LocalDateTime;
import java.util.UUID;

public record ProductSummaryResponse(
        UUID productId,
        String productName,
        String productImageUrl,
        SourceType sourceType,
        ProcessingStatus processingStatus,
        ResultStatus resultStatus,
        LocalDateTime createdAt
) {
}
