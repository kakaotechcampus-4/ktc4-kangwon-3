package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductFailureReason;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;

import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class AiResumeRequestUseCaseTest {

    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final String RUN_ID = "run-1";
    private static final String NEW_RUN_ID = "run-2";

    @Mock
    private AiDiagnosesClient aiDiagnosesClient;

    @Mock
    private DiagnosesService diagnosesService;

    @Mock
    private ProductService productService;

    @InjectMocks
    private AiResumeRequestUseCase aiResumeRequestUseCase;

    @Test
    @DisplayName("질문으로 끝난 실행 ID와 회차, 질문 키별 답변으로 AI에 재진단을 요청한다.")
    void requestResume_thenRequestWithQuestionKeys() {
        // given
        given(aiDiagnosesClient.requestResume(any())).willReturn(accepted());

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        ArgumentCaptor<AiResumeRequest> captor = ArgumentCaptor.forClass(AiResumeRequest.class);
        then(aiDiagnosesClient).should().requestResume(captor.capture());
        assertThat(captor.getValue()).isEqualTo(new AiResumeRequest(
                DIAGNOSES_ID.toString(), PRODUCT_ID.toString(), RUN_ID, 1, List.of(
                new AiResumeRequest.Answer("sales_type", "구매대행"),
                new AiResumeRequest.Answer("battery_only", "네"))));
    }

    @Test
    @DisplayName("AI가 접수하면 응답의 새 실행 식별자를 저장한다.")
    void requestResume_whenAccepted_thenAssignNewRun() {
        // given
        given(aiDiagnosesClient.requestResume(any())).willReturn(accepted());

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(diagnosesService).should().assignRuns(DIAGNOSES_ID, Map.of(PRODUCT_ID, NEW_RUN_ID));
        then(productService).should(never()).failDiagnoses(any(), any(), any(), any(), any(), any(), any());
        then(productService).should(never()).markResumePending(any(), any(), any());
    }

    @Test
    @DisplayName("AI 응답에 새 실행 식별자가 없으면 저장하지 않는다.")
    void requestResume_whenAcceptedWithoutRunId_thenSkipAssign() {
        // given
        given(aiDiagnosesClient.requestResume(any()))
                .willReturn(new AiResumeAccepted(PRODUCT_ID.toString(), null, "accepted"));

        // when & then
        assertThatCode(() -> aiResumeRequestUseCase.requestResume(event(), false)).doesNotThrowAnyException();
        then(diagnosesService).should(never()).assignRuns(any(), any());
    }

    @Test
    @DisplayName("새 실행 식별자 저장에 실패해도 예외를 밖으로 던지지 않는다.")
    void requestResume_whenAssignFails_thenSwallow() {
        // given
        given(aiDiagnosesClient.requestResume(any())).willReturn(accepted());
        willThrow(new BaseException(CommonResponseCode.CONFLICT))
                .given(diagnosesService).assignRuns(any(), any());

        // when & then
        assertThatCode(() -> aiResumeRequestUseCase.requestResume(event(), false)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("AI 세션이 없으면(404) 다시 진단할 수 있는 실패로 처리한다.")
    void requestResume_whenSessionNotFound_thenFailAsRetryable() {
        // given
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(rejected(HttpStatus.NOT_FOUND, ProductFailureReason.RESUME_SESSION_NOT_FOUND.getCode()));

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(productService).should().failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, null,
                ProductFailureReason.RESUME_SESSION_NOT_FOUND.getCode(),
                ProductFailureReason.RESUME_SESSION_NOT_FOUND.getMessage(), true);
        then(diagnosesService).should(never()).assignRuns(any(), any());
    }

    @ParameterizedTest
    @CsvSource({
            "BAD_REQUEST, AI_UNKNOWN_QUESTION_KEY, RESUME_UNKNOWN_QUESTION_KEY",
            "UNPROCESSABLE_CONTENT, AI_INVALID_REQUEST, RESUME_INVALID_REQUEST",
            "CONFLICT, AI_RESUME_CONFLICT, RESUME_CONFLICT",
            "UNAUTHORIZED, AI_UNAUTHORIZED, RESUME_UNAUTHORIZED"
    })
    @DisplayName("처음 보낸 요청을 AI가 거절하거나(400·422) 기다리는 질문과 어긋났다고 하거나(409) 내부 토큰이 틀렸다고 하면(401) 다시 진단할 수 없는 실패로 처리한다.")
    void requestResume_whenRejected_thenFailAsNotRetryable(HttpStatus status, String code, ProductFailureReason reason) {
        // given
        given(aiDiagnosesClient.requestResume(any())).willThrow(rejected(status, code));

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(productService).should().failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, null,
                code, reason.getMessage(), false);
    }

    @Test
    @DisplayName("다시 보낸 요청이 충돌(409)하면 처음 요청이 접수됐을 수 있어 다시 진단할 수 있는 실패로 처리한다.")
    void requestResume_whenResendConflict_thenFailAsRetryable() {
        // given
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(rejected(HttpStatus.CONFLICT, ProductFailureReason.RESUME_RESEND_CONFLICT.getCode()));

        // when
        aiResumeRequestUseCase.requestResume(event(), true);

        // then
        then(productService).should().failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, null,
                ProductFailureReason.RESUME_RESEND_CONFLICT.getCode(),
                ProductFailureReason.RESUME_RESEND_CONFLICT.getMessage(), true);
    }

    @ParameterizedTest
    @EnumSource(value = HttpStatus.class, names = {"TOO_MANY_REQUESTS", "INTERNAL_SERVER_ERROR", "BAD_GATEWAY", "SERVICE_UNAVAILABLE"})
    @DisplayName("AI가 대기열 초과나 서버 오류로 응답하면 재요청 대기로 표시한다.")
    void requestResume_whenQueueFullOrServerError_thenMarkPending(HttpStatus status) {
        // given
        given(aiDiagnosesClient.requestResume(any())).willThrow(rejected(status, null));

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(productService).should().markResumePending(DIAGNOSES_ID, PRODUCT_ID, RUN_ID);
        then(productService).should(never()).failDiagnoses(any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("AI 연결에 실패하면 재요청 대기로 표시한다.")
    void requestResume_whenConnectionRefused_thenMarkPending() {
        // given
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(new ResourceAccessException("I/O error", new ConnectException("Connection refused")));

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(productService).should().markResumePending(DIAGNOSES_ID, PRODUCT_ID, RUN_ID);
    }

    @Test
    @DisplayName("응답을 읽다 시간이 초과되면 AI가 받았는지 몰라 다시 보내지 않고 상품 상태도 바꾸지 않는다.")
    void requestResume_whenReadTimeout_thenKeepState() {
        // given
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(new ResourceAccessException("I/O error", new SocketTimeoutException("Read timed out")));

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(productService).should(never()).markResumePending(any(), any(), any());
        then(productService).should(never()).failDiagnoses(any(), any(), any(), any(), any(), any(), any());
        then(diagnosesService).should(never()).assignRuns(any(), any());
    }

    @Test
    @DisplayName("알 수 없는 거절(501 등)은 다시 보내지 않고 상품 상태도 바꾸지 않는다.")
    void requestResume_whenUnknownRejection_thenKeepState() {
        // given
        given(aiDiagnosesClient.requestResume(any())).willThrow(rejected(HttpStatus.NOT_IMPLEMENTED, null));

        // when
        aiResumeRequestUseCase.requestResume(event(), false);

        // then
        then(productService).should(never()).markResumePending(any(), any(), any());
        then(productService).should(never()).failDiagnoses(any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("거절에 따른 실패 처리가 실패해도 예외를 밖으로 던지지 않는다.")
    void requestResume_whenFailDiagnosesFails_thenSwallow() {
        // given
        given(aiDiagnosesClient.requestResume(any()))
                .willThrow(rejected(HttpStatus.NOT_FOUND, ProductFailureReason.RESUME_SESSION_NOT_FOUND.getCode()));
        willThrow(new BaseException(CommonResponseCode.CONFLICT))
                .given(productService).failDiagnoses(any(), any(), any(), isNull(), any(), any(), anyBoolean());

        // when & then
        assertThatCode(() -> aiResumeRequestUseCase.requestResume(event(), false)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("재요청 대기 표시가 실패해도 예외를 밖으로 던지지 않는다.")
    void requestResume_whenMarkPendingFails_thenSwallow() {
        // given
        given(aiDiagnosesClient.requestResume(any())).willThrow(rejected(HttpStatus.SERVICE_UNAVAILABLE, null));
        willThrow(new RuntimeException("lock timeout"))
                .given(productService).markResumePending(any(), any(), any());

        // when & then
        assertThatCode(() -> aiResumeRequestUseCase.requestResume(event(), false)).doesNotThrowAnyException();
    }

    private AiResumeRequestedEvent event() {
        return new AiResumeRequestedEvent(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1, List.of(
                new AiResumeRequestedEvent.Answer("sales_type", "구매대행"),
                new AiResumeRequestedEvent.Answer("battery_only", "네")));
    }

    private AiResumeAccepted accepted() {
        return new AiResumeAccepted(PRODUCT_ID.toString(), NEW_RUN_ID, "accepted");
    }

    // RestClient가 던지는 것처럼 본문을 AiApiResponse로 읽을 수 있는 오류 응답 예외. code가 null이면 본문이 없는 응답
    private RestClientResponseException rejected(HttpStatus status, String code) {
        RestClientResponseException exception = status.is4xxClientError()
                ? HttpClientErrorException.create(status, status.getReasonPhrase(), HttpHeaders.EMPTY, new byte[0], null)
                : HttpServerErrorException.create(status, status.getReasonPhrase(), HttpHeaders.EMPTY, new byte[0], null);
        exception.setBodyConvertFunction(type -> code == null ? null : new AiApiResponse<>(code, "거절되었습니다.", null));
        return exception;
    }
}
