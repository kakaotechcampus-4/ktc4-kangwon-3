package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.util.List;

public record DiagnosesCreateRequest(

        @NotBlank(message = "제품명은 필수입니다.")
        @Size(max = 100, message = "제품명은 100자를 넘을 수 없습니다.")
        String productName,

        @Size(max = 2048, message = "이미지 URL이 너무 깁니다.")
        String productImageUrl,

        @NotNull(message = "등록 방식은 필수입니다.")
        SourceType sourceType,

        String sourceUrl,

        String sourceText,

        @Size(max = 20, message = "이미지는 최대 20장까지 등록할 수 있습니다.")
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

