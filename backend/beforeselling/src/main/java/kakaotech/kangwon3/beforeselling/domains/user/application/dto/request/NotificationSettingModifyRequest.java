package kakaotech.kangwon3.beforeselling.domains.user.application.dto.request;

import jakarta.validation.constraints.NotNull;

public record NotificationSettingModifyRequest(
        @NotNull Boolean lawAmendmentAlertEnabled
) {
}
