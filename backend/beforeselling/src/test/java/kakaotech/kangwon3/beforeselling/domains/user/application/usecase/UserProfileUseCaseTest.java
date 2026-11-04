package kakaotech.kangwon3.beforeselling.domains.user.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.UserProfileModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.UserProfileResponse;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class UserProfileUseCaseTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private UserService userService;

    @InjectMocks
    private UserProfileUseCase userProfileUseCase;

    @Test
    @DisplayName("내 정보를 조회하면 이름, 이메일, 소셜 제공자를 반환한다.")
    void getMyProfile_thenReturnProfile() {
        // given
        given(userService.getUser(USER_ID)).willReturn(createUser("사용자"));

        // when
        UserProfileResponse response = userProfileUseCase.getMyProfile(USER_ID);

        // then
        assertThat(response).isEqualTo(new UserProfileResponse("사용자", "user@example.com", SocialProvider.KAKAO));
    }

    @Test
    @DisplayName("이름을 보내면 이름이 수정된 내 정보를 반환한다.")
    void modifyMyProfile_withName_thenReturnModifiedProfile() {
        // given
        given(userService.updateName(USER_ID, "새 이름")).willReturn(createUser("새 이름"));

        // when
        UserProfileResponse response = userProfileUseCase.modifyMyProfile(USER_ID, new UserProfileModifyRequest("새 이름"));

        // then
        assertThat(response.name()).isEqualTo("새 이름");
    }

    @Test
    @DisplayName("이름을 보내지 않으면 이름을 수정하지 않고 현재 정보를 반환한다.")
    void modifyMyProfile_withoutName_thenKeepProfile() {
        // given
        given(userService.getUser(USER_ID)).willReturn(createUser("사용자"));

        // when
        UserProfileResponse response = userProfileUseCase.modifyMyProfile(USER_ID, new UserProfileModifyRequest(null));

        // then
        assertThat(response.name()).isEqualTo("사용자");
        then(userService).should(never()).updateName(any(), anyString());
    }

    private User createUser(String name) {
        return User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", name);
    }
}
