package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;
import java.util.UUID;

public record ProductResponse(
        UUID productId,
        int sortOrder,
        String productName,
        String productImageUrl,
        SourceType sourceType,
        String sourceUrl,
        String sourceText,
        List<String> imageUrls,
        ProcessingStatus processingStatus,
        ResultStatus resultStatus,
        String summary
) {
}