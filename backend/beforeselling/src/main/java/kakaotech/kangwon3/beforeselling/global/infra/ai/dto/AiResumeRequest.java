package kakaotech.kangwon3.beforeselling.global.infra.ai.dto;

import java.util.List;

// AI 재진단 요청 DTO (POST /api/ai/v1/diagnose/resume)
public record AiResumeRequest(
        String diagnosisId,
        String productId,
        // 질문으로 끝난 실행 ID. AI가 중복·늦게 온 답변을 구분하는 데 쓴다.
        String runId,
        int questionRound,
        List<Answer> answers
) {
    public record Answer(
            String questionKey,
            String answerText
    ) {
    }
}
