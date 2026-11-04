package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.UserProfileModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.UserProfileResponse;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UserProfileUseCase {

    private final UserService userService;

    public UserProfileResponse getMyProfile(UUID userId) {
        return UserProfileResponse.from(userService.getUser(userId));
    }

    public UserProfileResponse modifyMyProfile(UUID userId, UserProfileModifyRequest request) {
        User user = request.name() == null
                ? userService.getUser(userId)
                : userService.updateName(userId, request.name());
        return UserProfileResponse.from(user);
    }
}
