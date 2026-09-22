package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;

import java.time.LocalDateTime;
import java.util.List;

public record DiagnosesDetailResponse(
        Long diagnosesId,
        ProcessingStatus processingStatus,
        List<ProductResponse> products,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}