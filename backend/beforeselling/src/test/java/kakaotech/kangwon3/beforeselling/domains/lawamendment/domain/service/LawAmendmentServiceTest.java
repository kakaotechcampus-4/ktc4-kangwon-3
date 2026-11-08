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
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.entry;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.times;

@ExtendWith(MockitoExtension.class)
class LawAmendmentServiceTest {

    @Mock
    private LawAmendmentRepository lawAmendmentRepository;

    @Mock
    private LawAmendmentProductRepository lawAmendmentProductRepository;

    @Mock
    private ProductService productService;

    @Mock
    private LawAmendmentMailService lawAmendmentMailService;

    @InjectMocks
    private LawAmendmentService lawAmendmentService;

    @Captor
    private ArgumentCaptor<List<LawAmendmentProduct>> recheckProductsCaptor;

    @Captor
    private ArgumentCaptor<Map<LawAmendment, List<Product>>> recheckProductsByAmendmentCaptor;

    @Test
    @DisplayName("법령 변경을 받으면 저장하고 그 분야 검토에서 해당 법령을 인용한 상품을 재확인 대상으로 지정해 메일로 알린다.")
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
        then(lawAmendmentMailService).should().sendLawAmendmentMails(Map.of(lawAmendment, List.of(product)));
    }

    @Test
    @DisplayName("법령 변경을 여러 건 받으면 모두 반영한 뒤 메일 발송은 한 번에 모아서 요청한다.")
    void createLawAmendments_withMany_thenRequestMailsOnce() {
        // given
        LawAmendment act = createLawAmendment("화장품법", "000001", "100001");
        LawAmendment rule = createLawAmendment("화장품법 시행규칙", "000002", "100002");
        Product product = createProduct();
        given(lawAmendmentRepository.save(any())).willAnswer(invocation -> invocation.getArgument(0));
        given(productService.findCompletedByToolNameAndCitedLawName(ToolName.CHILDREN, "화장품법"))
                .willReturn(List.of(product));
        given(productService.findCompletedByToolNameAndCitedLawName(ToolName.CHILDREN, "화장품법 시행규칙"))
                .willReturn(List.of(product));

        // when
        List<LawAmendment> created = lawAmendmentService.createLawAmendments(List.of(act, rule));

        // then
        assertThat(created).containsExactly(act, rule);
        then(lawAmendmentMailService).should(times(1)).sendLawAmendmentMails(recheckProductsByAmendmentCaptor.capture());
        assertThat(recheckProductsByAmendmentCaptor.getValue())
                .containsExactly(entry(act, List.of(product)), entry(rule, List.of(product)));
    }

    @Test
    @DisplayName("이미 받은 변경을 다시 받으면 저장하지 않고 재확인 대상 지정도 다시 하지 않으며 메일 발송 대상에서도 뺀다.")
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
        then(lawAmendmentMailService).should().sendLawAmendmentMails(Map.of());
    }

    @Test
    @DisplayName("회원의 재확인 대상 상품을 조회한다.")
    void getRecheckProducts_thenReturnOfUser() {
        // given
        UUID userId = UUID.randomUUID();
        List<LawAmendmentProduct> recheckProducts = List.of(
                LawAmendmentProduct.of(createLawAmendment(), createProduct()));
        given(lawAmendmentProductRepository.findWithLawAmendmentAndProductByUserId(userId)).willReturn(recheckProducts);

        // when & then
        assertThat(lawAmendmentService.getRecheckProducts(userId)).isEqualTo(recheckProducts);
    }

    @Test
    @DisplayName("상품을 재확인 대상에서 빼면 그 상품의 연결을 모두 지운다.")
    void removeRecheckProducts_thenDeleteByProduct() {
        // given
        UUID productId = UUID.randomUUID();

        // when
        lawAmendmentService.removeRecheckProducts(productId);

        // then
        then(lawAmendmentProductRepository).should().deleteByProductId(productId);
    }

    private LawAmendment createLawAmendment() {
        return createLawAmendment("어린이제품 안전 특별법 시행규칙", "012345", "291321");
    }

    private LawAmendment createLawAmendment(String lawName, String documentId, String serialNumber) {
        return LawAmendment.builder()
                .lawName(lawName)
                .documentId(documentId)
                .admrul(false)
                .toolName(ToolName.CHILDREN)
                .serialNumber(serialNumber)
                .build();
    }

    private Product createProduct() {
        return Product.pending("대나무 헬리콥터", null, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null);
    }
}
