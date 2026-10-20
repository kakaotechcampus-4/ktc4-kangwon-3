package kakaotech.kangwon3.beforeselling.global.infra.ai.dto;

// AI 재진단 접수 응답(202)의 data.
public record AiResumeAccepted(
        String productId,
        String runId,
        String status
) {
}
