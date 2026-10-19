package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.ArraySchema;
import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;

import java.util.List;
import java.util.UUID;

public record ProductResponse(
        @Schema(example = "0b9f3c2e-6d1a-4f7b-9c8e-2a5d4e3f1b6c")
        UUID productId,

        @Schema(description = "업로드 순서(0부터)", example = "0")
        int sortOrder,

        @Schema(example = "무선 블루투스 이어폰")
        String productName,

        @Schema(example = "https://beforeselling.s3.ap-northeast-2.amazonaws.com/product-main/1/0b9f3c2e_thumbnail.jpg")
        String productImageUrl,

        @Schema(example = "URL")
        SourceType sourceType,

        @Schema(description = "sourceType이 URL일 때만 값이 있음", example = "https://www.made-in-china.com/showroom/example/product-detailabc123/Wireless-Bluetooth-Earbuds.html")
        String sourceUrl,

        @Schema(description = "sourceType이 TEXT_IMAGE일 때만 값이 있음", example = "블루투스 5.3 무선 이어폰, 충전 케이스 포함, 배터리 400mAh")
        String sourceText,

        @ArraySchema(schema = @Schema(example = "https://beforeselling.s3.ap-northeast-2.amazonaws.com/product-detail/1/0b9f3c2e_detail1.jpg"))
        List<String> imageUrls,

        @Schema(example = "COMPLETED")
        ProcessingStatus processingStatus,

        @Schema(description = "결과를 받기 전에는 null", example = "COMPLETED")
        AssessmentStatus assessmentStatus,

        @Schema(description = "결과를 받기 전에는 null", example = "DIRECT_IMPORT_CERTIFICATION_REQUIRED")
        ResultStatus resultStatus,

        @Schema(description = "결과를 받기 전에는 null", example = "블루투스 무선기기로 전파법상 적합성평가 대상이라 사입 전 KC 전파인증이 필요합니다.")
        String summary,

        // 이하 진단 결과. 결과를 받기 전에는 빈 목록.
        List<ProductToolReviewResponse> toolReviews,

        @ArraySchema(schema = @Schema(example = "국립전파연구원에 적합성평가(KC 전파인증)를 신청하세요."))
        List<String> requiredActions,

        @ArraySchema(schema = @Schema(example = "구매대행으로 판매해도 개인 사용 목적 면제 요건을 확인해야 합니다."))
        List<String> notices
) {
}
