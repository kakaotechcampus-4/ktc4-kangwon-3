package kakaotech.kangwon3.beforeselling.global.exception;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.PessimisticLockingFailureException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.stream.Stream;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 컨트롤러에서 던진 예외가 공통 응답 형식(상태 코드 + 서비스 코드)으로 바뀌는지 검증한다.
 * 스프링 컨텍스트 없이 예외를 던지는 테스트용 컨트롤러와 GlobalExceptionHandler만 등록한다.
 */
class GlobalExceptionHandlerTest {

    private final MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new ThrowingController())
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    static Stream<Arguments> exceptions() {
        return Stream.of(
                Arguments.of("client-base", CommonResponseCode.NOT_FOUND),
                Arguments.of("server-base", CommonResponseCode.INTERNAL_SERVER_ERROR),
                Arguments.of("data-integrity", CommonResponseCode.DATA_INTEGRITY_VIOLATION),
                Arguments.of("access-denied", CommonResponseCode.FORBIDDEN),
                Arguments.of("lock-timeout", CommonResponseCode.LOCK_CONFLICT),
                Arguments.of("unexpected", CommonResponseCode.INTERNAL_SERVER_ERROR)
        );
    }

    @ParameterizedTest(name = "{0} → {1}")
    @MethodSource("exceptions")
    @DisplayName("처리 중 예외가 발생하면 예외 종류에 맞는 상태 코드와 서비스 코드로 응답한다.")
    void handleException_thenMappedResponse(String type, BaseResponseCode expected) throws Exception {
        // when & then
        mockMvc.perform(get("/throw/{type}", type))
                .andExpect(status().is(expected.getStatus().value()))
                .andExpect(jsonPath("$.code").value(expected.getCode()))
                .andExpect(jsonPath("$.message").value(expected.getMessage()));
    }

    @Test
    @DisplayName("지원하지 않는 HTTP 메서드로 요청하면 405와 METHOD_NOT_ALLOWED 코드로 응답한다.")
    void handleMethodNotSupported_thenMethodNotAllowed() throws Exception {
        // when & then
        mockMvc.perform(post("/throw/{type}", "unexpected"))
                .andExpect(status().isMethodNotAllowed())
                .andExpect(jsonPath("$.code").value(CommonResponseCode.METHOD_NOT_ALLOWED.getCode()));
    }

    @RestController
    static class ThrowingController {

        @GetMapping("/throw/{type}")
        void throwException(@PathVariable String type) {
            switch (type) {
                case "client-base" -> throw new BaseException(CommonResponseCode.NOT_FOUND);
                case "server-base" -> throw new BaseException(CommonResponseCode.INTERNAL_SERVER_ERROR);
                case "data-integrity" -> throw new DataIntegrityViolationException("duplicate key");
                case "access-denied" -> throw new AccessDeniedException("denied");
                case "lock-timeout" -> throw new PessimisticLockingFailureException("lock timeout");
                default -> throw new IllegalStateException("unexpected");
            }
        }
    }
}
