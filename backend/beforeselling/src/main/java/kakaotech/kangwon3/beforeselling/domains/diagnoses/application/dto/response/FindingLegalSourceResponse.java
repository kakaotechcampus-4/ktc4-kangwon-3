package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.UUID;

// 판단 항목의 법령·기관 근거
public record FindingLegalSourceResponse(
        @Schema(example = "5a9c1e3f-7b2d-4c6e-8f0a-1b2c3d4e5f6a")
        UUID findingLegalSourceId,

        @Schema(example = "국가법령정보센터")
        String sourceName,

        @Schema(description = "없으면 null", example = "전파법")
        String lawName,

        @Schema(description = "없으면 null", example = "제58조의2 제1항")
        String article,

        @Schema(description = "근거 원문 인용. 없으면 null", example = "방송통신기자재등을 제조 또는 판매하거나 수입하려는 자는 해당 기자재에 대하여 적합성평가를 받아야 한다.")
        String quotedText,

        @Schema(description = "없으면 null", example = "https://www.law.go.kr/법령/전파법")
        String sourceUrl,

        @Schema(description = "AI가 준 문자열 그대로라 날짜 형식이 보장되지 않음. 없으면 null", example = "2025-01-21")
        String effectiveDate
) {
}
