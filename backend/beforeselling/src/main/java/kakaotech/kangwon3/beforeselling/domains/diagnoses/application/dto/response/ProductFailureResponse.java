package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response;

import io.swagger.v3.oas.annotations.media.Schema;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;

// 진단 실패 정보
public record ProductFailureResponse(
        @Schema(description = "실패한 단계. 진단 시작 전 실패나 결과를 받지 못해 종료한 경우 null", example = "TOOL_EXECUTION")
        PipelineStage failedStage,

        @Schema(description = """
                AI가 보낸 오류 코드 또는 BE가 직접 실패 처리한 코드.
                - BE: BE_DIAGNOSES_TIMEOUT(결과를 받지 못함), BE_AI_REQUEST_UNAVAILABLE(AI 서버가 요청을 받지 못함),
                  BE_AI_REQUEST_REJECTED(AI 서버가 요청을 거절함), BE_AI_REQUEST_CONFLICT(이전 진단이 아직 진행 중),
                  BE_AI_RESUME_UNAVAILABLE(AI 서버가 답변을 받지 못함)
                - AI 진단 실패: AI_PIPELINE_ERROR(진단 중 오류), AI_TIMEOUT(진단 시간 초과),
                  AI_UNSUPPORTED_SITE(지원하지 않는 사이트 URL), AI_SOURCE_FETCH_FAILED(상세페이지 수집 실패),
                  AI_EMPTY_SOURCE(상세페이지에 읽을 내용이 없음)
                - AI 재진단 거절: AI_SESSION_NOT_FOUND(진단 세션이 사라짐), AI_UNKNOWN_QUESTION_KEY(묻지 않은 질문의 답변),
                  AI_INVALID_REQUEST(요청 형식 오류), AI_RESUME_CONFLICT(답변을 기다리는 질문이 아님),
                  AI_UNAUTHORIZED(내부 토큰 오류)""",
                example = "AI_TIMEOUT")
        String errorCode,

        @Schema(example = "진단 시간이 초과되었습니다.")
        String errorMessage,

        @Schema(description = "다시 진단하면 성공할 수 있는지. 알 수 없으면 null", example = "true")
        Boolean retryable
) {
}
