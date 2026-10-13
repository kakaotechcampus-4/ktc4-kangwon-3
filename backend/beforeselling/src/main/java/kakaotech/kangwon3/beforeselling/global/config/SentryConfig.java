package kakaotech.kangwon3.beforeselling.global.config;

import io.sentry.SentryOptions;
import jakarta.validation.ConstraintViolationException;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.springframework.beans.TypeMismatchException;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.ErrorResponse;
import io.sentry.SentryBaseEvent;
import io.sentry.protocol.Request;
import kakaotech.kangwon3.beforeselling.global.security.filter.InternalTokenFilter;

@Configuration
public class SentryConfig {

    // 4xx은 클라이언트 요청 문제라 모두 노이즈로 보고 차단하고, 5xx만 전송
    // exception-resolver-order를 최우선으로 두어 GlobalExceptionHandler보다 먼저 예외를 캡처
    @Bean
    public SentryOptions.BeforeSendCallback sentryBeforeSendCallback() {
        return (event, _) -> {
            HttpStatusCode status = resolveStatus(event.getThrowable());
            if (status != null && status.is4xxClientError()) {
                return null;
            }
            removeInternalToken(event);
            return event;
        };
    }

    // 트레이스(traces-sample-rate)에도 요청 헤더가 실리므로 같은 헤더를 지운다.
    @Bean
    public SentryOptions.BeforeSendTransactionCallback sentryBeforeSendTransactionCallback() {
        return (transaction, _) -> {
            removeInternalToken(transaction);
            return transaction;
        };
    }

    // 캡처 시점엔 아직 응답 상태가 없으므로, GlobalExceptionHandler와 같은 기준으로 예외에서 상태코드를 추론
    private static HttpStatusCode resolveStatus(Throwable throwable) {
        return switch (throwable) {
            case BaseException e -> e.getResponseCode().getStatus();
            // NoResourceFoundException(404) 등 Spring이 던지는 ErrorResponse 구현 예외
            case ErrorResponse e -> e.getStatusCode();
            // ErrorResponse 미구현이라 상태코드를 직접 못 읽고 GlobalExceptionHandler에서 고정 매핑하는 예외
            case AccessDeniedException _ -> CommonResponseCode.FORBIDDEN.getStatus();
            case ConstraintViolationException _, TypeMismatchException _ ->
                    CommonResponseCode.INVALID_METHOD_ARGUMENT.getStatus();
            case HttpMessageNotReadableException _ -> CommonResponseCode.BAD_REQUEST.getStatus();
            case DataIntegrityViolationException _ -> CommonResponseCode.DATA_INTEGRITY_VIOLATION.getStatus();
            case PessimisticLockingFailureException _ -> CommonResponseCode.LOCK_CONFLICT.getStatus();
            case null, default -> null;
        };
    }

    // send-default-pii로 요청 헤더가 전송되는데, Sentry 기본 마스킹은 X-Internal-Token을 모름
    private static void removeInternalToken(SentryBaseEvent event) {
        Request request = event.getRequest();
        if (request == null || request.getHeaders() == null) {
            return;
        }
        request.getHeaders().keySet().removeIf(InternalTokenFilter.HEADER_NAME::equalsIgnoreCase);
    }
}
