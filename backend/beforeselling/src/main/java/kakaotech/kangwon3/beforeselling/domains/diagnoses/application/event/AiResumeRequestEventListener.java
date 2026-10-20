package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientResponseException;

import java.util.Map;

/**
 * 사용자 답변이 커밋된 뒤 AI에 재진단을 요청하고, 접수 응답(202)의 새 실행 식별자를 저장한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiResumeRequestEventListener {

    // AI 재진단 거절 응답의 code
    static final String SESSION_NOT_FOUND = "AI_SESSION_NOT_FOUND";
    static final String UNKNOWN_QUESTION_KEY = "AI_UNKNOWN_QUESTION_KEY";
    static final String INVALID_REQUEST = "AI_INVALID_REQUEST";
    static final String RESUME_CONFLICT = "AI_RESUME_CONFLICT";

    static final String SESSION_NOT_FOUND_MESSAGE = "답변을 기다리는 시간이 지나 진단을 이어갈 수 없습니다. 다시 진단해 주세요.";
    static final String REJECTED_MESSAGE = "진단을 이어서 진행하지 못했습니다.";

    private final AiDiagnosesClient aiDiagnosesClient;
    private final DiagnosesService diagnosesService;
    private final ProductService productService;

    @Async
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handle(AiResumeRequestedEvent event) {
        AiResumeAccepted accepted;
        try {
            accepted = aiDiagnosesClient.requestResume(toRequest(event));
        } catch (RestClientResponseException e) {
            handleRejected(event, e);
            return;
        } catch (Exception e) {
            // TODO: AI 429·5xx·연결 실패 처리(#335 후속). 지금은 상품이 IN_PROGRESS로 남고 멈춘 진단 정리(#330)에 맡긴다.
            log.error("AI 재진단 요청 실패. diagnosesId={}, productId={}, runId={}",
                    event.diagnosesId(), event.productId(), event.runId(), e);
            return;
        }

        if (accepted == null || !StringUtils.hasText(accepted.runId())) {
            log.error("AI 재진단 접수 응답에 실행 식별자가 없습니다. diagnosesId={}, productId={}",
                    event.diagnosesId(), event.productId());
            return;
        }

        try {
            diagnosesService.assignRuns(event.diagnosesId(), Map.of(event.productId(), accepted.runId()));
        } catch (Exception e) {
            // 202를 받기 전에 멈춘 진단 정리로 실패 처리됐거나 상품이 삭제된 경우
            log.warn("재진단 실행 식별자 저장 실패. diagnosesId={}, productId={}, newRunId={}",
                    event.diagnosesId(), event.productId(), accepted.runId(), e);
        }
    }

    // AI 응답 code별 처리
    private void handleRejected(AiResumeRequestedEvent event, RestClientResponseException e) {
        String code = readCode(e);
        switch (code) {
            // 세션이 사라져(AI 재시작, 답변 대기 24시간 경과) 이어서 진단할 수 없다. 처음부터 다시 진단하면 접수된다.
            case SESSION_NOT_FOUND -> fail(event, code, SESSION_NOT_FOUND_MESSAGE, true);
            // BE가 잘못 보낸 요청
            case UNKNOWN_QUESTION_KEY, INVALID_REQUEST -> {
                log.error("AI가 재진단 요청을 거절했습니다. diagnosesId={}, productId={}, status={}, code={}, body={}",
                        event.diagnosesId(), event.productId(), e.getStatusCode(), code,
                        e.getResponseBodyAsString());
                fail(event, code, REJECTED_MESSAGE, false);
            }
            // 이미 접수됐거나(202 유실 뒤 재요청) 지난 질문에 대한 답변
            case RESUME_CONFLICT -> log.warn("AI가 재진단 요청을 중복으로 판단했습니다. diagnosesId={}, productId={}, runId={}",
                    event.diagnosesId(), event.productId(), event.runId());
            // 429·5xx 등. TODO: AI 요청 실패 처리(#335 후속). 지금은 멈춘 진단 정리(#330)에 맡긴다.
            case null, default -> log.error("AI 재진단 요청 실패. diagnosesId={}, productId={}, status={}, code={}",
                    event.diagnosesId(), event.productId(), e.getStatusCode(), code);
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
