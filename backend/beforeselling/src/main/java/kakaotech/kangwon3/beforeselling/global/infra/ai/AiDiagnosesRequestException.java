package kakaotech.kangwon3.beforeselling.global.infra.ai;

import lombok.Getter;

import java.util.List;

/**
 * AI 진단 요청 실패 예외
 */
@Getter
public class AiDiagnosesRequestException extends RuntimeException {

    public enum Failure {
        // AI가 요청을 받지 않은 경우(429, 5xx, 연결 실패). 재전송 가능.
        NOT_RECEIVED,
        // 요청은 보냈지만 접수됐는지 모르는 경우(읽기 타임아웃 등). 재전송 시 중복 요청으로 처리될 수 있음.
        UNKNOWN,
        // 재전송해도 같은 이유로 실패하는 경우(400, 404, 405, 422, 501 등).
        REJECTED,
        // 이미 진행 중인 상품이 섞여 진단서 전체를 거절한 경우(409).
        CONFLICT
    }

    private final Failure failure;
    // 로그용. 응답을 받지 못했으면 null
    private final Integer status;
    // CONFLICT일 때만 반환되는 값.
    private final List<String> conflictProductIds;

    private AiDiagnosesRequestException(Failure failure, Integer status, List<String> conflictProductIds,
                                        Throwable cause) {
        super("AI 진단 요청 실패. failure=" + failure + ", status=" + status, cause);
        this.failure = failure;
        this.status = status;
        this.conflictProductIds = conflictProductIds;
    }

    public static AiDiagnosesRequestException of(Failure failure, Integer status, Throwable cause) {
        return new AiDiagnosesRequestException(failure, status, List.of(), cause);
    }

    public static AiDiagnosesRequestException conflict(List<String> conflictProductIds, Throwable cause) {
        return new AiDiagnosesRequestException(Failure.CONFLICT, 409, List.copyOf(conflictProductIds), cause);
    }
}
