package kakaotech.kangwon3.beforeselling.domains.user.domain.service;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.repository.UserRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.never;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private UserService userService;

    @Test
    @DisplayName("존재하는 회원 ID로 조회하면 회원을 반환한다.")
    void getUser_thenReturnUser() {
        // given
        User user = createUser(USER_ID);
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(user));

        // when
        User result = userService.getUser(USER_ID);

        // then
        assertThat(result).isEqualTo(user);
    }

    @Test
    @DisplayName("존재하지 않는 회원 ID로 조회하면 NOT_FOUND 예외가 발생한다.")
    void getUser_withUnknownId_thenThrow() {
        // given
        given(userRepository.findById(USER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> userService.getUser(USER_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("이미 가입된 소셜 사용자로 조회하면 기존 회원을 반환하고 isNewUser는 false다.")
    void getOrCreateUser_withExistingSocialUser_thenReturnExistingUser() {
        // given
        User user = createUser(USER_ID);
        given(userRepository.findBySocialProviderAndSocialId(SocialProvider.KAKAO, "social-id"))
                .willReturn(Optional.of(user));

        // when
        UserLookupResult result = userService.getOrCreateUser(
                SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");

        // then
        assertThat(result.user()).isEqualTo(user);
        assertThat(result.isNewUser()).isFalse();
        then(userRepository).should(never()).saveAndFlush(org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("가입되지 않은 소셜 사용자로 조회하면 신규 가입시키고 isNewUser는 true다.")
    void getOrCreateUser_withNewSocialUser_thenCreateUser() {
        // given
        User newUser = createUser(USER_ID);
        given(userRepository.findBySocialProviderAndSocialId(SocialProvider.KAKAO, "social-id"))
                .willReturn(Optional.empty());
        given(userRepository.saveAndFlush(org.mockito.ArgumentMatchers.any(User.class))).willReturn(newUser);

        // when
        UserLookupResult result = userService.getOrCreateUser(
                SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");

        // then
        assertThat(result.user()).isEqualTo(newUser);
        assertThat(result.isNewUser()).isTrue();
    }

    @Test
    @DisplayName("회원을 탈퇴 처리하면 저장소에서 삭제된다.")
    void withdraw_thenDeleteUser() {
        // given
        User user = createUser(USER_ID);
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(user));

        // when
        userService.withdraw(USER_ID);

        // then
        then(userRepository).should().delete(user);
    }

    @Test
    @DisplayName("존재하지 않는 회원을 탈퇴 처리하면 NOT_FOUND 예외가 발생하고 삭제가 호출되지 않는다.")
    void withdraw_withUnknownId_thenThrow() {
        // given
        given(userRepository.findById(USER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> userService.withdraw(USER_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
        then(userRepository).should(never()).delete(org.mockito.ArgumentMatchers.any());
    }

    @Test
    @DisplayName("소셜 로그인 성공 시 refresh_token을 갱신한다.")
    void updateSocialRefreshToken_thenUpdate() {
        // given
        User user = createUser(USER_ID);
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(user));

        // when
        userService.updateSocialRefreshToken(USER_ID, "new-refresh-token");

        // then
        assertThat(user.getSocialRefreshToken()).isEqualTo("new-refresh-token");
    }

    @Test
    @DisplayName("같은 소셜 계정으로 동시에 가입해 저장이 충돌하면, 먼저 가입된 회원을 다시 조회해 반환한다.")
    void getOrCreateUser_whenConcurrentSignup_thenReturnSavedUser() {
        // given
        User saved = createUser(USER_ID);
        given(userRepository.findBySocialProviderAndSocialId(SocialProvider.KAKAO, "social-id"))
                .willReturn(Optional.empty(), Optional.of(saved));
        given(userRepository.saveAndFlush(any(User.class)))
                .willThrow(new DataIntegrityViolationException("duplicate social account"));

        // when
        UserLookupResult result = userService.getOrCreateUser(
                SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");

        // then
        assertThat(result.user()).isEqualTo(saved);
    }

    @Test
    @DisplayName("저장 충돌 후 다시 조회해도 회원이 없으면 충돌 예외를 그대로 던진다.")
    void getOrCreateUser_whenConflictButUserMissing_thenRethrow() {
        // given
        DataIntegrityViolationException conflict = new DataIntegrityViolationException("duplicate social account");
        given(userRepository.findBySocialProviderAndSocialId(SocialProvider.KAKAO, "social-id"))
                .willReturn(Optional.empty());
        given(userRepository.saveAndFlush(any(User.class))).willThrow(conflict);

        // when & then
        assertThatThrownBy(() -> userService.getOrCreateUser(
                SocialProvider.KAKAO, "social-id", "user@example.com", "사용자"))
                .isSameAs(conflict);
    }

    @Test
    @DisplayName("회원 이름을 수정하면 앞뒤 공백을 제거한 이름으로 바뀐다.")
    void updateName_thenTrimmedNameApplied() {
        // given
        User user = createUser(USER_ID);
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(user));

        // when
        User result = userService.updateName(USER_ID, "  새 이름  ");

        // then
        assertThat(result.getName()).isEqualTo("새 이름");
    }

    @Test
    @DisplayName("존재하지 않는 회원의 이름을 수정하면 NOT_FOUND 예외가 발생한다.")
    void updateName_withUnknownId_thenThrow() {
        // given
        given(userRepository.findById(USER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> userService.updateName(USER_ID, "새 이름"))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    private User createUser(UUID id) {
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "id", id);
        return user;
    }

    @Test
    @DisplayName("개정 알림 수신을 끄면 회원의 수신 여부가 꺼진다.")
    void updateLawAmendmentAlertEnabled_thenChanged() {
        // given
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "홍길동");
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(user));

        // when
        User result = userService.updateLawAmendmentAlertEnabled(USER_ID, false);

        // then
        assertThat(result.isLawAmendmentAlertEnabled()).isFalse();
    }
}
