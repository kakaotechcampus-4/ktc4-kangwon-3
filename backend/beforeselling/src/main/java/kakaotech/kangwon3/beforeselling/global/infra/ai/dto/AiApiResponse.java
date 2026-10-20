package kakaotech.kangwon3.beforeselling.global.infra.ai.dto;

// AI 서버 공통 응답 형식
public record AiApiResponse<T>(
        String code,
        String message,
        T data
) {
}
