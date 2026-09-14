package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;

public record DiagnosesCreateCommand(
        Long userId,
        String productName,
        String productImageUrl,
        SourceType sourceType,
        String sourceUrl,
        String sourceText,
        List<String> imageUrls
) {
}
