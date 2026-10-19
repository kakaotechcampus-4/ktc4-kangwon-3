package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Determination;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.RiskLevel;

import java.util.List;
import java.util.UUID;

// 결과 카드 안의 판단 항목 하나
public record ProductFindingResponse(
        @Schema(example = "8e2d4f6a-1c3b-4e5d-9a7f-0b1c2d3e4f5a")
        UUID productFindingId,

        @Schema(example = "전파 적합성평가")
        String subject,

        @Schema(example = "REQUIRED")
        Determination determination,

        @Schema(example = "HIGH")
        RiskLevel riskLevel,

        @Schema(example = "2.4GHz 무선기기라 KC 적합성평가(적합인증)를 받아야 합니다.")
        String summary,

        @Schema(example = "2.4GHz RF 송수신 기능이 있어 방송통신기자재 적합성평가 대상입니다.")
        String rationale,

        List<FindingLegalSourceResponse> legalSources
) {
}
