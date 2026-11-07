package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.NotificationSettingModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.NotificationSettingResponse;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class NotificationSettingUseCase {

    private final UserService userService;

    public NotificationSettingResponse getMyNotificationSetting(UUID userId) {
        return NotificationSettingResponse.from(userService.getUser(userId));
    }

    public NotificationSettingResponse modifyMyNotificationSetting(UUID userId, NotificationSettingModifyRequest request) {
        return NotificationSettingResponse.from(
                userService.updateLawAmendmentAlertEnabled(userId, request.lawAmendmentAlertEnabled()));
    }
}
