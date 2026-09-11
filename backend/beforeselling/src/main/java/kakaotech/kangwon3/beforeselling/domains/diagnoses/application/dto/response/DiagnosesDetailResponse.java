package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.*;

import java.time.LocalDateTime;
import java.util.List;

public record DiagnosesDetailResponse(
        Long diagnosesId,
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

    public static DiagnosesDetailResponse of(Diagnoses diagnoses, List<DiagnosesImage> images) {
        List<String> imageUrls = images.stream()
                .map(DiagnosesImage::getImageUrl)
                .toList();

        return new DiagnosesDetailResponse(
                diagnoses.getId(),
                diagnoses.getProductName(),
                diagnoses.getProductImageUrl(),
                diagnoses.getSourceType(),
                diagnoses.getSourceUrl(),
                diagnoses.getSourceText(),
                imageUrls,
                diagnoses.getProcessingStatus(),
                diagnoses.getResultStatus(),
                diagnoses.getSummary(),
                diagnoses.getCreatedAt(),
                diagnoses.getUpdatedAt()
        );
    }
}
