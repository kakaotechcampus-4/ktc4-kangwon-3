package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record ProductAnswerRequest(
        @NotEmpty(message = "답변을 최소 한 개 이상 입력해야 합니다.")
        @Size(max = 20, message = "답변은 최대 20개까지 보낼 수 있습니다.")
        List<@Valid @NotNull(message = "답변은 비어 있을 수 없습니다.") Answer> answers
) {
    public record Answer(

            @NotNull(message = "질문 ID는 필수입니다.")
            UUID questionId,

            // 답변은 AI 진단 입력으로 그대로 들어가므로 길이를 제한한다.
            @NotBlank(message = "답변은 필수입니다.")
            @Size(max = 500, message = "답변은 500자를 넘을 수 없습니다.")
            String answerText
    ) {

    }
    @JsonIgnore
    @AssertTrue(message = "같은 질문에 두 번 답할 수 없습니다.")
    public boolean isQuestionIdsUnique() {
        if (answers == null) {
            return true;
        }
        List<UUID> questionIds = answers.stream()
                .filter(Objects::nonNull)
                .map(Answer::questionId)
                .toList();
        return questionIds.stream().distinct().count() == questionIds.size();
    }
}
