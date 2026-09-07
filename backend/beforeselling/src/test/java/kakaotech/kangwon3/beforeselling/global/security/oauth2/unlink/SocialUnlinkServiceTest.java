package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

class SocialUnlinkServiceTest {

    @Test
    @DisplayName("User의 provider에 해당하는 client에게 unlink를 위임한다.")
    void unlink_thenDelegateToMatchingProviderClient() {
        // given
        SocialUnlinkClient kakaoClient = Mockito.mock(SocialUnlinkClient.class);
        SocialUnlinkClient naverClient = Mockito.mock(SocialUnlinkClient.class);
        given(kakaoClient.provider()).willReturn(SocialProvider.KAKAO);
        given(naverClient.provider()).willReturn(SocialProvider.NAVER);

        SocialUnlinkService service = new SocialUnlinkService(List.of(kakaoClient, naverClient));
        User user = User.socialSignup(SocialProvider.NAVER, "naver-social-id", "user@example.com", "사용자");

        // when
        service.unlink(user);

        // then
        then(naverClient).should().unlink(user);
        then(kakaoClient).should(Mockito.never()).unlink(user);
    }

    @Test
    @DisplayName("등록되지 않은 provider면 예외 없이 건너뛴다.")
    void unlink_withUnregisteredProvider_thenSkipWithoutException() {
        // given
        SocialUnlinkClient kakaoClient = Mockito.mock(SocialUnlinkClient.class);
        given(kakaoClient.provider()).willReturn(SocialProvider.KAKAO);

        SocialUnlinkService service = new SocialUnlinkService(List.of(kakaoClient));
        User user = User.socialSignup(SocialProvider.GOOGLE, "google-social-id", "user@example.com", "사용자");

        // when & then
        assertThatCode(() -> service.unlink(user)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("client가 예외를 던져도 흡수하고 전파하지 않는다.")
    void unlink_whenClientThrows_thenAbsorbException() {
        // given
        SocialUnlinkClient kakaoClient = Mockito.mock(SocialUnlinkClient.class);
        given(kakaoClient.provider()).willReturn(SocialProvider.KAKAO);
        willThrow(new RuntimeException("provider API 오류")).given(kakaoClient).unlink(org.mockito.ArgumentMatchers.any());

        SocialUnlinkService service = new SocialUnlinkService(List.of(kakaoClient));
        User user = User.socialSignup(SocialProvider.KAKAO, "kakao-social-id", "user@example.com", "사용자");

        // when & then
        assertThatCode(() -> service.unlink(user)).doesNotThrowAnyException();
    }
}
