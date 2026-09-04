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
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.never;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private UserService userService;

    @Test
    @DisplayName("존재하는 회원 ID로 조회하면 회원을 반환한다.")
    void getUser_thenReturnUser() {
        // given
        User user = createUser(1L);
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        // when
        User result = userService.getUser(1L);

        // then
        assertThat(result).isEqualTo(user);
    }

    @Test
    @DisplayName("존재하지 않는 회원 ID로 조회하면 NOT_FOUND 예외가 발생한다.")
    void getUser_withUnknownId_thenThrow() {
        // given
        given(userRepository.findById(1L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> userService.getUser(1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("회원을 탈퇴 처리하면 저장소에서 삭제된다.")
    void withdraw_thenDeleteUser() {
        // given
        User user = createUser(1L);
        given(userRepository.findById(1L)).willReturn(Optional.of(user));

        // when
        userService.withdraw(1L);

        // then
        then(userRepository).should().delete(user);
    }

    @Test
    @DisplayName("존재하지 않는 회원을 탈퇴 처리하면 NOT_FOUND 예외가 발생하고 삭제가 호출되지 않는다.")
    void withdraw_withUnknownId_thenThrow() {
        // given
        given(userRepository.findById(1L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> userService.withdraw(1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
        then(userRepository).should(never()).delete(org.mockito.ArgumentMatchers.any());
    }

    private User createUser(Long id) {
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "id", id);
        return user;
    }
}
