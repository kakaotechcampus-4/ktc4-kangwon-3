package kakaotech.kangwon3.beforeselling.domains.user.domain.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Arrays;
import java.util.Optional;

@Getter
@RequiredArgsConstructor
public enum SocialProvider {

    KAKAO("kakao"),
    NAVER("naver"),
    GOOGLE("google"),
    ;

    private final String registrationId;

    public static Optional<SocialProvider> fromRegistrationId(String registrationId) {
        return Arrays.stream(values())
                .filter(provider -> provider.registrationId.equalsIgnoreCase(registrationId))
                .findFirst();
    }
}
