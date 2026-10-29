package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.util.Map;

/**
 * AI에 재진단을 요청하고, 접수(202)면 새 실행 식별자를 저장한다.
 * AI가 요청을 받지 못하면(429·5xx·연결 실패) 재요청 대기로 표시해 재요청 스케줄러가 다시 보내게 한다.
 * 답변 제출 직후(AiResumeRequestEventListener)와 재요청(PendingResumeRetryScheduler)에서 사용한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AiResumeRequestUseCase {

    // AI 재진단 거절 응답의 code
    static final String SESSION_NOT_FOUND = "AI_SESSION_NOT_FOUND";
    static final String UNKNOWN_QUESTION_KEY = "AI_UNKNOWN_QUESTION_KEY";
    static final String INVALID_REQUEST = "AI_INVALID_REQUEST";
    static final String RESUME_CONFLICT = "AI_RESUME_CONFLICT";
    static final String UNAUTHORIZED = "AI_UNAUTHORIZED";

    static final String SESSION_NOT_FOUND_MESSAGE = "진단 정보를 찾을 수 없어 이어서 진행할 수 없습니다. 다시 진단해 주세요.";
    static final String REJECTED_MESSAGE = "진단을 이어서 진행하지 못했습니다.";
    static final String RESEND_CONFLICT_MESSAGE = "진단을 이어서 진행하지 못했습니다. 다시 시도해 주세요.";

    private final AiDiagnosesClient aiDiagnosesClient;
    private final DiagnosesService diagnosesService;
    private final ProductService productService;

    /**
     * @param resend 재요청 스케줄러가 다시 보내는 요청인지. 다시 보낸 요청의 409는 처음 요청이 이미 접수됐을 수 있다.
     */
    public void requestResume(AiResumeRequestedEvent event, boolean resend) {
        try {
            AiResumeAccepted accepted = aiDiagnosesClient.requestResume(toRequest(event));
            assignRun(event, accepted);
        } catch (RestClientResponseException e) {
            handleRejected(event, e, resend);
        } catch (RestClientException e) {
            handleNotAccepted(event, e);
        } catch (Exception e) {
            log.error("AI 재진단 요청 처리 실패. diagnosesId={}, productId={}, runId={}",
                    event.diagnosesId(), event.productId(), event.runId(), e);
        }
    }

    private void assignRun(AiResumeRequestedEvent event, AiResumeAccepted accepted) {
        if (accepted == null || !StringUtils.hasText(accepted.runId())) {
            log.error("AI 재진단 접수 응답에 실행 식별자가 없습니다. diagnosesId={}, productId={}",
                    event.diagnosesId(), event.productId());
            return;
        }

        try {
            diagnosesService.assignRuns(event.diagnosesId(), Map.of(event.productId(), accepted.runId()));
        } catch (Exception e) {
            log.warn("재진단 실행 식별자 저장 실패. diagnosesId={}, productId={}, newRunId={}",
                    event.diagnosesId(), event.productId(), accepted.runId(), e);
        }
    }

    // AI 응답 code별 처리
    private void handleRejected(AiResumeRequestedEvent event, RestClientResponseException e, boolean resend) {
        String code = readCode(e);
        // 처음 요청을 AI가 실제로는 받아 실행 중인 경우일 수 있다. 실행 식별자를 몰라 결과를 받을 수 없으므로 다시 진단하게 한다.
        if (resend && RESUME_CONFLICT.equals(code)) {
            log.warn("다시 보낸 재진단 요청이 충돌했습니다. 처음 요청이 접수됐을 수 있습니다. diagnosesId={}, productId={}, runId={}",
                    event.diagnosesId(), event.productId(), event.runId());
            fail(event, code, RESEND_CONFLICT_MESSAGE, true);
            return;
        }

        switch (code) {
            // 세션이 사라져(AI 재시작, 답변 대기 24시간 경과) 이어서 진단할 수 없다. 처음부터 다시 진단하면 접수된다.
            case SESSION_NOT_FOUND -> fail(event, code, SESSION_NOT_FOUND_MESSAGE, true);
            // BE가 잘못 보낸 요청
            case UNKNOWN_QUESTION_KEY, INVALID_REQUEST, RESUME_CONFLICT, UNAUTHORIZED -> {
                log.error("AI가 재진단 요청을 거절했습니다. diagnosesId={}, productId={}, status={}, code={}, body={}",
                        event.diagnosesId(), event.productId(), e.getStatusCode(), code,
                        e.getResponseBodyAsString());
                fail(event, code, REJECTED_MESSAGE, false);
            }
            case null, default -> handleNotAccepted(event, e);
        }
    }

    // 받지 못한 것이 확실하면(429·5xx·연결 실패) 재요청 대기로 표시해 다시 보낸다.
    // 받았는지 모르면 대기 표시를 바꾸지 않는다. 처음 요청이면 다시 보내지 않고 멈춘 진단 정리에 맡기고,
    // 재요청 중이었다면 표시가 남아 다음 재요청에서 다시 보낸다. AI가 이미 받았다면 그 재요청은 409로 끝난다.
    private void handleNotAccepted(AiResumeRequestedEvent event, RestClientException e) {
        if (!AiDiagnosesClient.isNotReceived(e)) {
            log.error("AI가 재진단 요청을 받았는지 알 수 없어 재요청 대기 표시를 바꾸지 않습니다. diagnosesId={}, productId={}, runId={}",
                    event.diagnosesId(), event.productId(), event.runId(), e);
            return;
        }

        log.warn("AI가 재진단 요청을 받지 않아 재요청을 기다립니다. diagnosesId={}, productId={}, runId={}",
                event.diagnosesId(), event.productId(), event.runId(), e);
        try {
            productService.markResumePending(event.diagnosesId(), event.productId(), event.runId());
        } catch (Exception markFailure) {
            log.warn("재진단 재요청 대기 표시 실패. diagnosesId={}, productId={}",
                    event.diagnosesId(), event.productId(), markFailure);
        }
    }

    // 상품의 현재 runId가 아직 질문으로 끝난 실행이라 콜백과 같은 실패 처리 경로를 쓸 수 있다.
    private void fail(AiResumeRequestedEvent event, String errorCode, String errorMessage, boolean retryable) {
        try {
            productService.failDiagnoses(event.diagnosesId(), event.productId(), event.runId(),
                    null, errorCode, errorMessage, retryable);
        } catch (Exception e) {
            log.warn("재진단 거절에 따른 실패 처리 실패. diagnosesId={}, productId={}, errorCode={}",
                    event.diagnosesId(), event.productId(), errorCode, e);
        }
    }

    // 오류 응답 본문의 code
    private String readCode(RestClientResponseException e) {
        try {
            AiApiResponse<?> body = e.getResponseBodyAs(AiApiResponse.class);
            return body == null ? null : body.code();
        } catch (Exception parseFailure) {
            return null;
        }
    }

    private AiResumeRequest toRequest(AiResumeRequestedEvent event) {
        return new AiResumeRequest(
                event.diagnosesId().toString(),
                event.productId().toString(),
                event.runId(),
                event.questionRound(),
                event.answers().stream()
                        .map(answer -> new AiResumeRequest.Answer(answer.questionKey(), answer.answerText()))
                        .toList());
    }
}
