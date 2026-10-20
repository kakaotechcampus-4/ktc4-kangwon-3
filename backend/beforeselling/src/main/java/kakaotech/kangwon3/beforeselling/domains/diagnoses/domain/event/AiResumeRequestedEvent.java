package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event;

import java.util.List;
import java.util.UUID;

/**
 * 사용자 답변이 커밋된 뒤 AI에 재진단을 요청하기 위한 이벤트.
 */
public record AiResumeRequestedEvent(
        UUID diagnosesId,
        UUID productId,
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
