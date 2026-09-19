package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;

public record DiagnosesCreateCommand(
        Long userId,
        String productName,
        String productImageKey,
        SourceType sourceType,
        String sourceUrl,
        String sourceText,
        List<String> imageKeys
) {
}
