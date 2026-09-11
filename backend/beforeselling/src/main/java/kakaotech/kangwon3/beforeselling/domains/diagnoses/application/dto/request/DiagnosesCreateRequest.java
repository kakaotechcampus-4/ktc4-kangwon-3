package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesCreateCommand;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.util.List;

public record DiagnosesCreateRequest (

        @NotBlank(message = "제품명은 필수입니다.")
        String productName,

        String productImageUrl,

        @NotNull(message = "등록 방식은 필수입니다.")
        SourceType sourceType,

        String sourceUrl,

        String sourceText,

        List<@NotBlank(message = "이미지 URL은 비어 있을 수 없습니다.") String> imageUrls
) {
        @JsonIgnore
        @AssertTrue(message = "URL 등록 시 상세페이지 URL은 필수입니다.")
        public boolean isSourceUrlProvidedForUrlType() {
            return sourceType != SourceType.URL || StringUtils.hasText(sourceUrl);
        }

        @JsonIgnore
        @AssertTrue(message = "텍스트 또는 이미지 중 하나는 반드시 입력해야 합니다.")
        public boolean isContentProvidedForTextImageType() {
            return sourceType != SourceType.TEXT_IMAGE
                    || StringUtils.hasText(sourceText)
                    || !CollectionUtils.isEmpty(imageUrls);
        }

    }

