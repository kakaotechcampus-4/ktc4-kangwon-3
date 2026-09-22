package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

import java.util.List;

public record DiagnosesCreateRequest(

        @NotEmpty(message = "진단할 상품을 최소 한 개 이상 등록해야 합니다.")
        @Size(max = 10, message = "상품은 최대 10개까지 등록할 수 있습니다.")
        List<@Valid ProductCreateRequest> products
) {
}