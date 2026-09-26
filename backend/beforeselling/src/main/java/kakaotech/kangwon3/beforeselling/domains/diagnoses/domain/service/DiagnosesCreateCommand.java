package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;
import java.util.UUID;

public record DiagnosesCreateCommand(
        UUID userId,
        String productName,
        String productImageKey,
        SourceType sourceType,
        String sourceUrl,
        String sourceText,
        List<String> imageKeys
) {
}
