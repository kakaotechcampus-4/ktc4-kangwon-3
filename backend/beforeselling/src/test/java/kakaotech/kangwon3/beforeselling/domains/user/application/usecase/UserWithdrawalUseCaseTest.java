package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink.SocialUnlinkService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.inOrder;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class UserWithdrawalUseCaseTest {

    @Mock
    private UserService userService;

    @Mock
    private AuthTokenService authTokenService;

    @Mock
    private SocialUnlinkService socialUnlinkService;

    @InjectMocks
    private UserWithdrawalUseCase userWithdrawalUseCase;

    @Test
    @DisplayName("회원 탈퇴를 요청하면 회원을 조회하고, 소셜 연동을 해제한 뒤, 회원 정보를 삭제하고, 리프레시 토큰을 폐기한다.")
    void withdraw_thenUnlinkThenDeleteUserAndRemoveRefreshToken() {
        // given
        User user = createUser(1L);
        given(userService.getUser(1L)).willReturn(user);

        // when
        userWithdrawalUseCase.withdraw(1L, "refresh-token");

        // then
        InOrder inOrder = inOrder(userService, socialUnlinkService, authTokenService);
        then(userService).should(inOrder).getUser(1L);
        then(socialUnlinkService).should(inOrder).unlink(user);
        then(userService).should(inOrder).withdraw(1L);
        then(authTokenService).should(inOrder).removeRefreshToken("refresh-token");
    }

    @Test
    @DisplayName("리프레시 토큰 쿠키가 없어도 회원 탈퇴는 정상적으로 처리된다.")
    void withdraw_withoutRefreshToken_thenStillDeleteUser() {
        // given
        User user = createUser(1L);
        given(userService.getUser(1L)).willReturn(user);

        // when
        userWithdrawalUseCase.withdraw(1L, null);

        // then
        then(socialUnlinkService).should().unlink(user);
        then(userService).should().withdraw(1L);
        then(authTokenService).should().removeRefreshToken(null);
    }

    private User createUser(Long id) {
        User user = User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "id", id);
        return user;
    }
}
