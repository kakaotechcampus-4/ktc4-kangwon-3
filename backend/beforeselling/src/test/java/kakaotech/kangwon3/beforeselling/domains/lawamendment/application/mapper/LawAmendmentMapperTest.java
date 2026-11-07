package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class LawAmendmentMapperTest {

    private final LawAmendmentMapper lawAmendmentMapper = new LawAmendmentMapper();

    @Test
    @DisplayName("법령 변경 콜백의 변경마다 받은 순서대로 법령 변경을 만든다.")
    void toLawAmendments_thenKeepOrderAndFields() {
        // given
        PublicLawChangeDto children = new PublicLawChangeDto("어린이제품 안전 특별법 시행규칙",
                "012345", false, ToolName.CHILDREN, "291321", "280000", "일부개정",
                LocalDate.of(2026, 10, 20), LocalDate.of(2026, 4, 20));
        PublicLawChangeDto electrical = new PublicLawChangeDto("전기용품 안전기준",
                "2100000", true, ToolName.ELECTRICAL, "300001", null, null, null, null);
        LawChangeCallbackRequest request = new LawChangeCallbackRequest(List.of(children, electrical));

        // when
        List<LawAmendment> result = lawAmendmentMapper.toLawAmendments(request);

        // then
        assertThat(result).hasSize(2);
        LawAmendment first = result.getFirst();
        assertThat(first.getLawName()).isEqualTo("어린이제품 안전 특별법 시행규칙");
        assertThat(first.getDocumentId()).isEqualTo("012345");
        assertThat(first.isAdmrul()).isFalse();
        assertThat(first.getToolName()).isEqualTo(ToolName.CHILDREN);
        assertThat(first.getSerialNumber()).isEqualTo("291321");
        assertThat(first.getPreviousSerialNumber()).isEqualTo("280000");
        assertThat(first.getRevisionType()).isEqualTo("일부개정");
        assertThat(first.getEnforceDate()).isEqualTo(LocalDate.of(2026, 10, 20));
        assertThat(first.getIssuedDate()).isEqualTo(LocalDate.of(2026, 4, 20));
        assertThat(result.get(1).getToolName()).isEqualTo(ToolName.ELECTRICAL);
        assertThat(result.get(1).isAdmrul()).isTrue();
    }
}
