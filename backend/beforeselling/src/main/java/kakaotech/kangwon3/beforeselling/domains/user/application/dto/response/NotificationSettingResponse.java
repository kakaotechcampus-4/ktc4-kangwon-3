package kakaotech.kangwon3.beforeselling.domains.user.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;

public record NotificationSettingResponse(
        boolean lawAmendmentAlertEnabled
) {

    public static NotificationSettingResponse from(User user) {
        return new NotificationSettingResponse(user.isLawAmendmentAlertEnabled());
    }
}
