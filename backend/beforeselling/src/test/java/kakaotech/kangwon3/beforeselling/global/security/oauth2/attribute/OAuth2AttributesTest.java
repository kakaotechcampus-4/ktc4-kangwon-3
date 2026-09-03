package kakaotech.kangwon3.beforeselling.global.security.oauth2.attribute;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OAuth2AttributesTest {

    @Test
    @DisplayName("카카오 응답에서 소셜 ID, 이메일, 닉네임을 추출한다.")
    void kakaoAttributes_thenExtract() {
        // given
        Map<String, Object> attributes = Map.of(
                "id", 1234567890L,
                "kakao_account", Map.of(
                        "email", "kakao@example.com",
                        "profile", Map.of("nickname", "카카오사용자")
                )
        );

        // when
        OAuth2Attributes result = OAuth2Attributes.of("kakao", attributes);

        // then
        assertThat(result).isInstanceOf(KakaoOAuth2Attributes.class);
        assertThat(result.getProvider()).isEqualTo(SocialProvider.KAKAO);
        assertThat(result.getSocialId()).isEqualTo("1234567890");
        assertThat(result.getEmail()).isEqualTo("kakao@example.com");
        assertThat(result.getName()).isEqualTo("카카오사용자");
    }

    @Test
    @DisplayName("카카오 응답에 이메일 동의 항목이 없으면 이메일은 null이다.")
    void kakaoAttributes_withoutEmail_thenEmailIsNull() {
        // given
        Map<String, Object> attributes = Map.of(
                "id", 1234567890L,
                "kakao_account", Map.of("profile", Map.of("nickname", "카카오사용자"))
        );

        // when
        OAuth2Attributes result = OAuth2Attributes.of("kakao", attributes);

        // then
        assertThat(result.getEmail()).isNull();
        assertThat(result.getName()).isEqualTo("카카오사용자");
    }

    @Test
    @DisplayName("네이버 응답의 response 객체에서 사용자 정보를 추출한다.")
    void naverAttributes_thenExtractFromResponse() {
        // given
        Map<String, Object> attributes = Map.of(
                "resultcode", "00",
                "message", "success",
                "response", Map.of(
                        "id", "naver-unique-id",
                        "email", "naver@example.com",
                        "name", "네이버사용자"
                )
        );

        // when
        OAuth2Attributes result = OAuth2Attributes.of("naver", attributes);

        // then
        assertThat(result).isInstanceOf(NaverOAuth2Attributes.class);
        assertThat(result.getProvider()).isEqualTo(SocialProvider.NAVER);
        assertThat(result.getSocialId()).isEqualTo("naver-unique-id");
        assertThat(result.getEmail()).isEqualTo("naver@example.com");
        assertThat(result.getName()).isEqualTo("네이버사용자");
    }

    @Test
    @DisplayName("구글 응답에서 sub, email, name을 추출한다.")
    void googleAttributes_thenExtract() {
        // given
        Map<String, Object> attributes = Map.of(
                "sub", "google-sub-id",
                "email", "google@example.com",
                "name", "구글사용자",
                "picture", "https://example.com/picture.png"
        );

        // when
        OAuth2Attributes result = OAuth2Attributes.of("google", attributes);

        // then
        assertThat(result).isInstanceOf(GoogleOAuth2Attributes.class);
        assertThat(result.getProvider()).isEqualTo(SocialProvider.GOOGLE);
        assertThat(result.getSocialId()).isEqualTo("google-sub-id");
        assertThat(result.getEmail()).isEqualTo("google@example.com");
        assertThat(result.getName()).isEqualTo("구글사용자");
    }

    @Test
    @DisplayName("지원하지 않는 제공자이면 UNSUPPORTED_SOCIAL_PROVIDER 예외가 발생한다.")
    void unsupportedProvider_thenThrow() {
        assertThatThrownBy(() -> OAuth2Attributes.of("apple", Map.of()))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(AuthResponseCode.UNSUPPORTED_SOCIAL_PROVIDER);
    }
}
