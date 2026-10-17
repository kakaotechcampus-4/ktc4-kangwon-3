package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;

import java.util.List;
import java.util.UUID;

// 결과 카드 안의 판단 항목 하나
public record ProductFindingResponse(
        UUID productFindingId,
        String subject,
        Determination determination,
        RiskLevel riskLevel,
        String summary,
        String rationale,
        List<FindingLegalSourceResponse> legalSources
) {
}
