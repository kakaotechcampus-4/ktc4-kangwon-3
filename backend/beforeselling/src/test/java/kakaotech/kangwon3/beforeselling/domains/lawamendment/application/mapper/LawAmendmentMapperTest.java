package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

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

    @Test
    @DisplayName("재확인 대상 상품을 법령 변경별로 묶고 조회 순서를 지킨다.")
    void toListResponse_thenGroupByLawAmendmentInOrder() {
        // given
        LawAmendment children = lawAmendment("어린이제품 안전 특별법 시행규칙", ToolName.CHILDREN);
        LawAmendment electrical = lawAmendment("전기용품 안전기준", ToolName.ELECTRICAL);
        Diagnoses firstDiagnoses = diagnoses();
        Diagnoses secondDiagnoses = diagnoses();
        Product toy = product(firstDiagnoses, "대나무 헬리콥터");
        Product doll = product(secondDiagnoses, "인형");
        Product charger = product(firstDiagnoses, "충전기");
        List<LawAmendmentProduct> recheckProducts = List.of(
                LawAmendmentProduct.of(children, toy),
                LawAmendmentProduct.of(electrical, charger),
                LawAmendmentProduct.of(children, doll));

        // when
        LawAmendmentListResponse response = lawAmendmentMapper.toListResponse(recheckProducts);

        // then
        assertThat(response.lawAmendments())
                .extracting(LawAmendmentResponse::lawAmendmentId, LawAmendmentResponse::lawName,
                        LawAmendmentResponse::revisionType, LawAmendmentResponse::toolName,
                        LawAmendmentResponse::enforceDate)
                .containsExactly(
                        tuple(children.getId(), "어린이제품 안전 특별법 시행규칙", "일부개정", ToolName.CHILDREN,
                                LocalDate.of(2026, 10, 20)),
                        tuple(electrical.getId(), "전기용품 안전기준", "일부개정", ToolName.ELECTRICAL,
                                LocalDate.of(2026, 10, 20)));
        assertThat(response.lawAmendments().getFirst().products())
                .extracting(LawAmendmentResponse.RecheckProductResponse::productId,
                        LawAmendmentResponse.RecheckProductResponse::diagnosesId,
                        LawAmendmentResponse.RecheckProductResponse::productName)
                .containsExactly(
                        tuple(toy.getId(), firstDiagnoses.getId(), "대나무 헬리콥터"),
                        tuple(doll.getId(), secondDiagnoses.getId(), "인형"));
        assertThat(response.lawAmendments().get(1).products())
                .extracting(LawAmendmentResponse.RecheckProductResponse::diagnosesId,
                        LawAmendmentResponse.RecheckProductResponse::productName)
                .containsExactly(tuple(firstDiagnoses.getId(), "충전기"));
    }

    @Test
    @DisplayName("재확인 대상 상품이 없으면 빈 목록을 만든다.")
    void toListResponse_withoutRecheckProducts_thenEmpty() {
        // when & then
        assertThat(lawAmendmentMapper.toListResponse(List.of()).lawAmendments()).isEmpty();
    }

    private LawAmendment lawAmendment(String lawName, ToolName toolName) {
        LawAmendment lawAmendment = LawAmendment.builder()
                .lawName(lawName)
                .documentId(lawName)
                .toolName(toolName)
                .serialNumber("291321")
                .revisionType("일부개정")
                .enforceDate(LocalDate.of(2026, 10, 20))
                .build();
        ReflectionTestUtils.setField(lawAmendment, "id", UUID.randomUUID());
        return lawAmendment;
    }

    private Diagnoses diagnoses() {
        Diagnoses diagnoses = Diagnoses.pending(UUID.randomUUID());
        ReflectionTestUtils.setField(diagnoses, "id", UUID.randomUUID());
        return diagnoses;
    }

    private Product product(Diagnoses diagnoses, String productName) {
        Product product = Product.pending(productName, null, SourceType.URL, "https://example.com", null);
        diagnoses.addProducts(List.of(product));
        ReflectionTestUtils.setField(product, "id", UUID.randomUUID());
        return product;
    }
}
