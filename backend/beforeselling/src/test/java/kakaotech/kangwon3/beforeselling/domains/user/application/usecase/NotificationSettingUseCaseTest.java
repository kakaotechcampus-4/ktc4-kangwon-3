package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.NotificationSettingModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.NotificationSettingResponse;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class NotificationSettingUseCaseTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private UserService userService;

    @InjectMocks
    private NotificationSettingUseCase notificationSettingUseCase;

    @Test
    @DisplayName("내 알림 설정을 조회하면 개정 알림 수신 여부를 돌려준다.")
    void getMyNotificationSetting_thenReturnAlertEnabled() {
        // given
        given(userService.getUser(USER_ID)).willReturn(createUser());

        // when
        NotificationSettingResponse response = notificationSettingUseCase.getMyNotificationSetting(USER_ID);

        // then
        assertThat(response.lawAmendmentAlertEnabled()).isTrue();
    }

    @Test
    @DisplayName("개정 알림 수신을 끄면 바뀐 수신 여부를 돌려준다.")
    void modifyMyNotificationSetting_thenReturnChanged() {
        // given
        User user = createUser();
        user.updateLawAmendmentAlertEnabled(false);
        given(userService.updateLawAmendmentAlertEnabled(USER_ID, false)).willReturn(user);

        // when
        NotificationSettingResponse response = notificationSettingUseCase.modifyMyNotificationSetting(
                USER_ID, new NotificationSettingModifyRequest(false));

        // then
        assertThat(response.lawAmendmentAlertEnabled()).isFalse();
    }

    private User createUser() {
        return User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "홍길동");
    }
}
