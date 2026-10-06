package kakaotech.kangwon3.beforeselling.global.config;

import io.sentry.Hint;
import io.sentry.SentryEvent;
import io.sentry.SentryOptions;
import io.sentry.exception.ExceptionMechanismException;
import io.sentry.protocol.Mechanism;
import jakarta.validation.ConstraintViolationException;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.TypeMismatchException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.http.HttpInputMessage;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.Set;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.springframework.http.HttpMethod.GET;

class SentryConfigTest {

    private final SentryOptions.BeforeSendCallback callback = new SentryConfig().sentryBeforeSendCallback();

    static Stream<Arguments> clientErrors() {
        return Stream.of(
                Arguments.of("BaseException 400", new BaseException(CommonResponseCode.BAD_REQUEST)),
                Arguments.of("BaseException 401", new BaseException(CommonResponseCode.UNAUTHORIZED)),
                Arguments.of("BaseException 409", new BaseException(CommonResponseCode.LOCK_CONFLICT)),
                Arguments.of("NoResourceFoundException", new NoResourceFoundException(GET, "/none", "none")),
                Arguments.of("HttpRequestMethodNotSupportedException", new HttpRequestMethodNotSupportedException("PATCH")),
                Arguments.of("AccessDeniedException", new AccessDeniedException("denied")),
                Arguments.of("ConstraintViolationException", new ConstraintViolationException(Set.of())),
                Arguments.of("TypeMismatchException", new TypeMismatchException("abc", Integer.class)),
                Arguments.of("HttpMessageNotReadableException",
                        new HttpMessageNotReadableException("bad json", mock(HttpInputMessage.class))),
                Arguments.of("PessimisticLockingFailureException", new PessimisticLockingFailureException("lock")),
                Arguments.of("DataIntegrityViolationException", new DataIntegrityViolationException("dup"))
        );
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("clientErrors")
    @DisplayName("4xx로 응답되는 예외는 Sentry로 전송하지 않는다.")
    void execute_whenClientError_thenDropEvent(String name, Throwable throwable) {
        // when & then
        assertThat(callback.execute(new SentryEvent(throwable), new Hint())).isNull();
    }

    @Test
    @DisplayName("Sentry가 ExceptionMechanismException으로 감싼 4xx 예외도 전송하지 않는다.")
    void execute_whenWrappedClientError_thenDropEvent() {
        // given
        Throwable wrapped = new ExceptionMechanismException(
                new Mechanism(), new BaseException(CommonResponseCode.NOT_FOUND), Thread.currentThread());

        // when & then
        assertThat(callback.execute(new SentryEvent(wrapped), new Hint())).isNull();
    }

    @Test
    @DisplayName("5xx BaseException은 그대로 전송한다.")
    void execute_whenServerErrorBaseException_thenKeepEvent() {
        // given
        SentryEvent event = new SentryEvent(new BaseException(CommonResponseCode.INTERNAL_SERVER_ERROR));

        // when & then
        assertThat(callback.execute(event, new Hint())).isSameAs(event);
    }

    @Test
    @DisplayName("상태코드를 알 수 없는 예외는 500으로 응답되므로 그대로 전송한다.")
    void execute_whenUnknownException_thenKeepEvent() {
        // given
        SentryEvent event = new SentryEvent(new IllegalStateException("boom"));

        // when & then
        assertThat(callback.execute(event, new Hint())).isSameAs(event);
    }

    @Test
    @DisplayName("예외 없이 메시지로만 생성된 이벤트는 그대로 전송한다.")
    void execute_whenNoThrowable_thenKeepEvent() {
        // given
        SentryEvent event = new SentryEvent();

        // when & then
        assertThat(callback.execute(event, new Hint())).isSameAs(event);
    }
}
