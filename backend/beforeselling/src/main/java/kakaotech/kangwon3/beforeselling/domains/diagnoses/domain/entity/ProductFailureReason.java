package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.List;

// BE가 상품을 실패 처리할 때의 오류 코드·문구·재시도 여부
@Getter
@RequiredArgsConstructor
public enum ProductFailureReason {

    // BE가 직접 실패 처리
    // AI_TIMEOUT과 같은 일시적인 실패라 다시 진단하면 성공할 수 있다.
    DIAGNOSES_TIMEOUT("BE_DIAGNOSES_TIMEOUT", "진단 결과를 받지 못해 진단을 종료했습니다.", true),
    // 대부분 BE 코드·설정 문제라 다시 진단해도 같은 결과다.
    AI_REQUEST_REJECTED("BE_AI_REQUEST_REJECTED", "진단 요청이 거절되어 진단을 시작하지 못했습니다.", false),
    // 재요청 기한까지 AI가 요청을 받지 못함. 일시적인 장애라 다시 진단하면 성공할 수 있다.
    AI_REQUEST_UNAVAILABLE("BE_AI_REQUEST_UNAVAILABLE", "AI 서버가 요청을 받지 못해 진단을 시작하지 못했습니다.", true),
    // AI가 같은 상품의 이전 진단을 진행 중이라(409) 받지 않음. 이전 진단이 끝나면 다시 진단할 수 있다.
    AI_REQUEST_CONFLICT("BE_AI_REQUEST_CONFLICT", "이전 진단이 아직 끝나지 않아 진단을 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.", true),
    // 재진단 요청을 기한까지 AI가 받지 못함. 일시적인 장애라 다시 진단하면 성공할 수 있다.
    AI_RESUME_UNAVAILABLE("BE_AI_RESUME_UNAVAILABLE", "AI 서버가 답변을 받지 못해 진단을 이어서 진행하지 못했습니다.", true),

    // AI 재진단 거절. 코드는 AI 응답 그대로, 문구·재시도 여부는 BE가 정한다.
    RESUME_SESSION_NOT_FOUND("AI_SESSION_NOT_FOUND", "진단 정보를 찾을 수 없어 이어서 진행할 수 없습니다. 다시 진단해 주세요.", true),
    RESUME_UNKNOWN_QUESTION_KEY("AI_UNKNOWN_QUESTION_KEY", "진단을 이어서 진행하지 못했습니다.", false),
    RESUME_INVALID_REQUEST("AI_INVALID_REQUEST", "진단을 이어서 진행하지 못했습니다.", false),
    RESUME_CONFLICT("AI_RESUME_CONFLICT", "진단을 이어서 진행하지 못했습니다.", false),
    RESUME_UNAUTHORIZED("AI_UNAUTHORIZED", "진단을 이어서 진행하지 못했습니다.", false),
    // 다시 보낸 요청의 충돌. 처음 요청이 접수됐을 수 있어 다시 진단하게 한다.
    RESUME_RESEND_CONFLICT("AI_RESUME_CONFLICT", "진단을 이어서 진행하지 못했습니다. 다시 시도해 주세요.", true),
    ;

    // 다시 보낸 요청의 충돌은 code가 같아 제외
    private static final List<ProductFailureReason> RESUME_REJECTIONS = List.of(
            RESUME_SESSION_NOT_FOUND, RESUME_UNKNOWN_QUESTION_KEY, RESUME_INVALID_REQUEST,
            RESUME_CONFLICT, RESUME_UNAUTHORIZED);

    private final String code;
    private final String message;
    private final boolean retryable;

    // AI 재진단 거절 응답 code의 실패 사유. 모르는 code면 null
    public static ProductFailureReason resumeRejectionOf(String code) {
        for (ProductFailureReason reason : RESUME_REJECTIONS) {
            if (reason.code.equals(code)) {
                return reason;
            }
        }
        return null;
    }
}
