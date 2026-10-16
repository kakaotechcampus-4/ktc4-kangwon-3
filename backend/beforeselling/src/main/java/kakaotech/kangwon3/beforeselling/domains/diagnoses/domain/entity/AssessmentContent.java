package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import java.util.List;

// AI가 보낸 상품 하나의 진단 결과 내용
public record AssessmentContent(
        AssessmentStatus status,
        ResultStatus resultStatus,
        String summary,
        List<ToolReviewContent> toolReviews,
        List<String> requiredActions,
        List<String> notices
) {

    public record ToolReviewContent(
            ToolName toolName,
            ToolReviewStatus status,
            String message,
            List<FindingContent> findings
    ) {
    }

    public record FindingContent(
            String subject,
            Determination determination,
            RiskLevel riskLevel,
            String summary,
            String rationale,
            List<LegalSourceContent> legalSources
    ) {
    }

    public record LegalSourceContent(
            String sourceName,
            String lawName,
            String article,
            String quotedText,
            String sourceUrl,
            String effectiveDate
    ) {
    }
}
