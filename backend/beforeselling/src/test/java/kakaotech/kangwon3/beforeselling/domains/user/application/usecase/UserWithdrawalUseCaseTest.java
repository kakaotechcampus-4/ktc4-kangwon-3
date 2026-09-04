package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.mockito.BDDMockito.inOrder;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class UserWithdrawalUseCaseTest {

    @Mock
    private UserService userService;

    @Mock
    private AuthTokenService authTokenService;

    @InjectMocks
    private UserWithdrawalUseCase userWithdrawalUseCase;

    @Test
    @DisplayName("회원 탈퇴를 요청하면 회원 정보를 먼저 삭제한 뒤 리프레시 토큰을 폐기한다.")
    void withdraw_thenDeleteUserAndRemoveRefreshToken() {
        // when
        userWithdrawalUseCase.withdraw(1L, "refresh-token");

        // then
        InOrder inOrder = inOrder(userService, authTokenService);
        then(userService).should(inOrder).withdraw(1L);
        then(authTokenService).should(inOrder).removeRefreshToken("refresh-token");
    }

    @Test
    @DisplayName("리프레시 토큰 쿠키가 없어도 회원 탈퇴는 정상적으로 처리된다.")
    void withdraw_withoutRefreshToken_thenStillDeleteUser() {
        // when
        userWithdrawalUseCase.withdraw(1L, null);

        // then
        then(userService).should().withdraw(1L);
        then(authTokenService).should().removeRefreshToken(null);
    }
}
