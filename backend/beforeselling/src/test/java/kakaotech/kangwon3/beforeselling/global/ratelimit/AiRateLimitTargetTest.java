package kakaotech.kangwon3.beforeselling.global.ratelimit;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller.DiagnosesController;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller.ProductController;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

class AiRateLimitTargetTest {

    static Stream<Arguments> aiEndpoints() {
        return Stream.of(
                Arguments.of(DiagnosesController.class, "createDiagnoses"),
                Arguments.of(ProductController.class, "answerQuestions"),
                Arguments.of(ProductController.class, "retryDiagnoses")
        );
    }

    @ParameterizedTest(name = "{0}.{1}")
    @MethodSource("aiEndpoints")
    @DisplayName("AI를 호출하는 API에는 AI 한도가 적용된다")
    void appliesAiPolicy(Class<?> controller, String methodName) {
        // given
        Method method = Arrays.stream(controller.getDeclaredMethods())
                .filter(m -> m.getName().equals(methodName))
                .findFirst()
                .orElseThrow();

        // when
        RateLimit rateLimit = method.getAnnotation(RateLimit.class);

        // then
        assertThat(rateLimit).isNotNull();
        assertThat(rateLimit.value()).isEqualTo(RateLimitPolicy.AI);
    }
}
