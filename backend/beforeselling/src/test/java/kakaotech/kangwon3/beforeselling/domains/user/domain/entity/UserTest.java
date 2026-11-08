package kakaotech.kangwon3.beforeselling.domains.user.domain.entity;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;

class UserTest {

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"   "})
    @DisplayName("소셜 계정에 이름이 없거나 비어 있으면 기본 이름으로 가입한다.")
    void socialSignup_withoutName_thenDefaultName(String name) {
        // when
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", name);

        // then
        assertThat(user.getName()).isEqualTo("사용자");
    }

    @Test
    @DisplayName("소셜 계정 이름은 앞뒤 공백을 지워 저장하고, 일반 회원 역할로 가입한다.")
    void socialSignup_withName_thenTrimmedNameAndUserRole() {
        // when
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "  홍길동  ");

        // then
        assertThat(user.getName()).isEqualTo("홍길동");
        assertThat(user.getRole()).isEqualTo(Role.USER);
    }

    @Test
    @DisplayName("새로 가입한 회원은 개정 알림을 받는다.")
    void socialSignup_thenLawAmendmentAlertEnabled() {
        // when
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "홍길동");

        // then
        assertThat(user.isLawAmendmentAlertEnabled()).isTrue();
    }

    @Test
    @DisplayName("개정 알림 수신을 끄면 수신 여부가 꺼짐으로 바뀐다.")
    void updateLawAmendmentAlertEnabled_thenChanged() {
        // given
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "홍길동");

        // when
        user.updateLawAmendmentAlertEnabled(false);

        // then
        assertThat(user.isLawAmendmentAlertEnabled()).isFalse();
    }
}
