package kakaotech.kangwon3.beforeselling.global.security.resolver;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.security.authentication.TestingAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;

import java.lang.reflect.Method;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class LoginUserArgumentResolverTest {

    private final LoginUserArgumentResolver resolver = new LoginUserArgumentResolver();

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    @Test
    @DisplayName("@LoginUser가 붙은 UserPrincipal 파라미터만 처리한다.")
    void supportsParameter_thenOnlyLoginUserPrincipal() throws Exception {
        // when & then
        assertThat(resolver.supportsParameter(parameterOf("loginUser", UserPrincipal.class))).isTrue();
        assertThat(resolver.supportsParameter(parameterOf("withoutAnnotation", UserPrincipal.class))).isFalse();
        assertThat(resolver.supportsParameter(parameterOf("otherType", String.class))).isFalse();
    }

    @Test
    @DisplayName("SecurityContext의 인증 주체를 그대로 주입한다.")
    void resolveArgument_withUserPrincipal_thenReturnPrincipal() {
        // given
        UserPrincipal principal = new UserPrincipal(UUID.randomUUID(), Role.USER);
        SecurityContextHolder.getContext().setAuthentication(new TestingAuthenticationToken(principal, null));

        // when
        Object resolved = resolver.resolveArgument(null, null, null, null);

        // then
        assertThat(resolved).isSameAs(principal);
    }

    @Test
    @DisplayName("인증 정보가 없으면 UNAUTHORIZED 예외가 발생한다.")
    void resolveArgument_withoutAuthentication_thenThrow() {
        // when & then
        assertThatThrownBy(() -> resolver.resolveArgument(null, null, null, null))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.UNAUTHORIZED);
    }

    @Test
    @DisplayName("인증 주체가 UserPrincipal이 아니면 UNAUTHORIZED 예외가 발생한다.")
    void resolveArgument_withOtherPrincipal_thenThrow() {
        // given
        SecurityContextHolder.getContext().setAuthentication(new TestingAuthenticationToken("anonymous", null));

        // when & then
        assertThatThrownBy(() -> resolver.resolveArgument(null, null, null, null))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.UNAUTHORIZED);
    }

    private MethodParameter parameterOf(String methodName, Class<?> parameterType) throws NoSuchMethodException {
        Method method = SampleController.class.getDeclaredMethod(methodName, parameterType);
        return new MethodParameter(method, 0);
    }

    @SuppressWarnings("unused")
    static class SampleController {

        void loginUser(@LoginUser UserPrincipal principal) {
        }

        void withoutAnnotation(UserPrincipal principal) {
        }

        void otherType(@LoginUser String principal) {
        }
    }
}
