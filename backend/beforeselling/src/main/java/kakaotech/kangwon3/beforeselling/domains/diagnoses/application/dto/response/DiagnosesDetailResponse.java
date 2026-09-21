package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

public record DiagnosesDetailResponse(
        UUID diagnosesId,
        String productName,
        String productImageUrl,
        SourceType sourceType,
        String sourceUrl,
        String sourceText,
        List<String> imageUrls,
        ProcessingStatus processingStatus,
        ResultStatus resultStatus,
        String summary,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
