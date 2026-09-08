package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.service.AuthTokenService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink.SocialUnlinkService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class UserWithdrawalUseCase {

    private final UserService userService;
    private final AuthTokenService authTokenService;
    private final SocialUnlinkService socialUnlinkService;

    public void withdraw(Long userId, String refreshToken) {
        User user = userService.getUser(userId);
        socialUnlinkService.unlink(user);
        userService.withdraw(userId);
        authTokenService.removeRefreshToken(refreshToken);
    }
}
