package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicAssessmentDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicFindingDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicLegalSourceDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.PublicToolReviewDto;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import org.springframework.stereotype.Component;

@Component
public class AiCallbackMapper {

    public AssessmentContent toContent(PublicAssessmentDto dto) {
        return new AssessmentContent(
                dto.status(),
                dto.resultStatus(),
                dto.summary(),
                dto.toolReviews().stream().map(this::toContent).toList(),
                dto.requiredActions(),
                dto.notices()
        );
    }

    private AssessmentContent.ToolReviewContent toContent(PublicToolReviewDto dto) {
        return new AssessmentContent.ToolReviewContent(
                dto.toolName(),
                dto.status(),
                dto.message(),
                dto.findings().stream().map(this::toContent).toList()
        );
    }

    private AssessmentContent.FindingContent toContent(PublicFindingDto dto) {
        return new AssessmentContent.FindingContent(
                dto.subject(),
                dto.determination(),
                dto.riskLevel(),
                dto.summary(),
                dto.rationale(),
                dto.legalSources().stream().map(this::toContent).toList()
        );
    }

    private AssessmentContent.LegalSourceContent toContent(PublicLegalSourceDto dto) {
        return new AssessmentContent.LegalSourceContent(
                dto.sourceName(),
                dto.lawName(),
                dto.article(),
                dto.quotedText(),
                dto.sourceUrl(),
                dto.effectiveDate()
        );
    }
}
