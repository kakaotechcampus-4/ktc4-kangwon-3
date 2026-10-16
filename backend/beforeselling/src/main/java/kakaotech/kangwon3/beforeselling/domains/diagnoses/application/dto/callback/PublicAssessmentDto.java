package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;

import java.util.List;

// 상품 하나의 진단 결과. 미완료면 resultStatus는 RECHECK_REQUIRED이고 notices에 이유가 온다.
// 미완료 규칙·분야 카드 중복 같은 필드 간 규칙은 결과를 반영하는 엔티티에서 검증한다.
public record PublicAssessmentDto(
        @NotNull AssessmentStatus status,
        @NotNull ResultStatus resultStatus,
        @NotBlank String summary,
        List<@NotNull @Valid PublicToolReviewDto> toolReviews,
        List<@NotBlank String> requiredActions,
        List<@NotBlank String> notices
) {

    // AI가 빈 목록을 생략해도 null 대신 빈 목록으로 다룬다.
    public PublicAssessmentDto {
        toolReviews = toolReviews == null ? List.of() : toolReviews;
        requiredActions = requiredActions == null ? List.of() : requiredActions;
        notices = notices == null ? List.of() : notices;
    }
}
