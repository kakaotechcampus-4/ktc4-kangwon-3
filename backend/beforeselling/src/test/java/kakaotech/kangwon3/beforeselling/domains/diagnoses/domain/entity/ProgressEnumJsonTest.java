package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.json.JsonTest;
import org.springframework.test.context.ActiveProfiles;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@JsonTest
@ActiveProfiles("test")
class ProgressEnumJsonTest {

    @Autowired
    private JsonMapper jsonMapper;

    @Test
    @DisplayName("AI가 보내는 소문자 단계 값을 enum으로 받는다.")
    void read_whenLowerCaseValue_thenConvert() {
        assertThat(jsonMapper.readValue("\"extraction\"", PipelineStage.class)).isEqualTo(PipelineStage.EXTRACTION);
        assertThat(jsonMapper.readValue("\"tool_execution\"", PipelineStage.class)).isEqualTo(PipelineStage.TOOL_EXECUTION);
        assertThat(jsonMapper.readValue("\"started\"", StageStatus.class)).isEqualTo(StageStatus.STARTED);
    }

    @ParameterizedTest(name = "{0}")
    @ValueSource(strings = {"\"pipeline\"", "\"unknown\"", "\"tool-execution\""})
    @DisplayName("정의되지 않은 단계 값은 거부한다.")
    void read_whenUndefinedValue_thenThrow(String json) {
        assertThatThrownBy(() -> jsonMapper.readValue(json, PipelineStage.class))
                .isInstanceOf(JacksonException.class);
    }

    @Test
    @DisplayName("JSON으로 내보낼 때는 다른 BE enum과 같이 상수 이름(대문자)을 쓴다.")
    void write_thenConstantName() {
        assertThat(jsonMapper.writeValueAsString(PipelineStage.TOOL_EXECUTION)).isEqualTo("\"TOOL_EXECUTION\"");
    }
}
