package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;

// AI 법령 점검 한 번에서 찾은 변경 묶음
public record LawChangeCallbackRequest(
        @NotEmpty List<@NotNull @Valid PublicLawChangeDto> changes
) {
}
