package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;
import java.util.UUID;

/**
 * 진단서 생성이 커밋된 뒤 AI에 진단을 요청하기 위한 이벤트.
 */
public record AiDiagnosesRequestedEvent(
        UUID diagnosesId,
        List<ProductInput> products
) {

    // imageKeys는 대표 이미지 → 상세 이미지 순서
    public record ProductInput(
            UUID productId,
            SourceType sourceType,
            String sourceUrl,
            String sourceText,
            List<String> imageKeys
    ) {
    }
}
