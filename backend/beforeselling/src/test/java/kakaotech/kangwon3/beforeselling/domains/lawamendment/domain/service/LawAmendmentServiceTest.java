package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentProductRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository.LawAmendmentRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class LawAmendmentServiceTest {

    @Mock
    private LawAmendmentRepository lawAmendmentRepository;

    @Mock
    private LawAmendmentProductRepository lawAmendmentProductRepository;

    @Mock
    private ProductService productService;

    @InjectMocks
    private LawAmendmentService lawAmendmentService;

    @Captor
    private ArgumentCaptor<List<LawAmendmentProduct>> recheckProductsCaptor;

    @Test
    @DisplayName("법령 변경을 받으면 저장하고 그 분야 검토에서 해당 법령을 인용한 상품을 재확인 대상으로 지정한다.")
    void createLawAmendments_thenSaveAndCreateRecheckProducts() {
        // given
        LawAmendment lawAmendment = createLawAmendment();
        Product product = createProduct();
        given(lawAmendmentRepository.save(lawAmendment)).willReturn(lawAmendment);
        given(productService.findCompletedByToolNameAndCitedLawName(ToolName.CHILDREN, "어린이제품 안전 특별법 시행규칙"))
                .willReturn(List.of(product));

        // when
        List<LawAmendment> created = lawAmendmentService.createLawAmendments(List.of(lawAmendment));

        // then
        assertThat(created).containsExactly(lawAmendment);
        then(lawAmendmentProductRepository).should().saveAll(recheckProductsCaptor.capture());
        assertThat(recheckProductsCaptor.getValue())
                .singleElement()
                .satisfies(recheckProduct -> {
                    assertThat(recheckProduct.getLawAmendment()).isEqualTo(lawAmendment);
                    assertThat(recheckProduct.getProduct()).isEqualTo(product);
                });
    }

    @Test
    @DisplayName("이미 받은 변경을 다시 받으면 저장하지 않고 재확인 대상도 다시 지정하지 않는다.")
    void createLawAmendments_withReceived_thenSkip() {
        // given
        LawAmendment lawAmendment = createLawAmendment();
        given(lawAmendmentRepository.existsByDocumentIdAndSerialNumber("012345", "291321")).willReturn(true);

        // when
        List<LawAmendment> created = lawAmendmentService.createLawAmendments(List.of(lawAmendment));

        // then
        assertThat(created).isEmpty();
        then(lawAmendmentRepository).should(never()).save(any());
        then(lawAmendmentProductRepository).should(never()).saveAll(any());
    }

    private LawAmendment createLawAmendment() {
        return LawAmendment.builder()
                .lawName("어린이제품 안전 특별법 시행규칙")
                .documentId("012345")
                .admrul(false)
                .toolName(ToolName.CHILDREN)
                .serialNumber("291321")
                .build();
    }

    private Product createProduct() {
        return Product.pending("대나무 헬리콥터", null, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null);
    }
}
