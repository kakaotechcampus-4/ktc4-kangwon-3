package kakaotech.kangwon3.beforeselling.domains.user.application.dto.response;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;

public record UserProfileResponse(
        String name,
        String email,
        SocialProvider socialProvider
) {

    public static UserProfileResponse from(User user) {
        return new UserProfileResponse(user.getName(), user.getEmail(), user.getSocialProvider());
    }
}
