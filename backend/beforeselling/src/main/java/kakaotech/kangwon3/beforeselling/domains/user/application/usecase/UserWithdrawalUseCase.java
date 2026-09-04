package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class UserWithdrawalUseCase {

    private final UserService userService;
    private final AuthTokenService authTokenService;

    public void withdraw(Long userId, String refreshToken) {
        userService.withdraw(userId);
        authTokenService.removeRefreshToken(refreshToken);
    }
}
