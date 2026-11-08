package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository;

import jakarta.persistence.EntityManager;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import kakaotech.kangwon3.beforeselling.global.config.JpaAuditingConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.CryptoProperties;
import kakaotech.kangwon3.beforeselling.global.security.crypto.DatabaseEncryptionConverter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Tag("integration")
@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({JpaAuditingConfig.class, DatabaseEncryptionConverter.class})
@EnableConfigurationProperties(CryptoProperties.class)
class LawAmendmentProductRepositoryTest {

    @Autowired
    private LawAmendmentRepository lawAmendmentRepository;

    @Autowired
    private LawAmendmentProductRepository lawAmendmentProductRepository;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private EntityManager entityManager;

    @Test
    @DisplayName("같은 법령 변경을 두 번 저장하면 무결성 위반으로 거부된다.")
    void saveSameLawAmendment_thenViolateUnique() {
        // given
        lawAmendmentRepository.saveAndFlush(createLawAmendment());

        // when & then
        assertThatThrownBy(() -> lawAmendmentRepository.saveAndFlush(createLawAmendment()))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("같은 법령 변경에 같은 상품을 두 번 연결하면 무결성 위반으로 거부된다.")
    void saveSameRecheckProduct_thenViolateUnique() {
        // given
        LawAmendment lawAmendment = lawAmendmentRepository.save(createLawAmendment());
        Product product = saveProduct();
        lawAmendmentProductRepository.saveAndFlush(LawAmendmentProduct.of(lawAmendment, product));

        // when & then
        assertThatThrownBy(() -> lawAmendmentProductRepository.saveAndFlush(
                LawAmendmentProduct.of(lawAmendment, product)))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("재확인 대상 상품을 삭제하면 재확인 연결도 함께 삭제된다.")
    void removeProduct_thenRemoveRecheckProduct() {
        // given
        LawAmendment lawAmendment = lawAmendmentRepository.save(createLawAmendment());
        Product product = saveProduct();
        lawAmendmentProductRepository.save(LawAmendmentProduct.of(lawAmendment, product));
        flushAndClear();

        // when
        Diagnoses diagnoses = diagnosesRepository.findAll().getFirst();
        diagnosesRepository.delete(diagnoses);
        flushAndClear();

        // then
        assertThat(lawAmendmentProductRepository.count()).isZero();
        assertThat(lawAmendmentRepository.count()).isOne();
    }

    @Test
    @DisplayName("회원의 재확인 대상 상품만 법령 변경과 함께 조회한다.")
    void findWithLawAmendmentAndProductByUserId_thenOnlyOfUser() {
        // given
        UUID userId = UUID.randomUUID();
        LawAmendment lawAmendment = lawAmendmentRepository.save(createLawAmendment());
        Product mine = saveProduct(userId, "내 상품");
        Product others = saveProduct(UUID.randomUUID(), "남의 상품");
        lawAmendmentProductRepository.save(LawAmendmentProduct.of(lawAmendment, mine));
        lawAmendmentProductRepository.save(LawAmendmentProduct.of(lawAmendment, others));
        flushAndClear();

        // when
        List<LawAmendmentProduct> result = lawAmendmentProductRepository.findWithLawAmendmentAndProductByUserId(userId);

        // then
        assertThat(result).singleElement().satisfies(recheckProduct -> {
            assertThat(recheckProduct.getProduct().getProductName()).isEqualTo("내 상품");
            assertThat(recheckProduct.getLawAmendment().getLawName()).isEqualTo("어린이제품 안전 특별법 시행규칙");
        });
    }

    @Test
    @DisplayName("상품의 재확인 연결을 지우면 다른 상품의 연결은 남는다.")
    void deleteByProductId_thenOnlyOfProduct() {
        // given
        LawAmendment lawAmendment = lawAmendmentRepository.save(createLawAmendment());
        Product target = saveProduct(UUID.randomUUID(), "재진단할 상품");
        Product other = saveProduct(UUID.randomUUID(), "그대로 둘 상품");
        lawAmendmentProductRepository.save(LawAmendmentProduct.of(lawAmendment, target));
        lawAmendmentProductRepository.save(LawAmendmentProduct.of(lawAmendment, other));
        flushAndClear();

        // when
        int deleted = lawAmendmentProductRepository.deleteByProductId(target.getId());

        // then
        assertThat(deleted).isOne();
        assertThat(lawAmendmentProductRepository.findAll())
                .extracting(recheckProduct -> recheckProduct.getProduct().getId())
                .containsExactly(other.getId());
    }

    private Product saveProduct(UUID userId, String productName) {
        Diagnoses diagnoses = Diagnoses.pending(userId);
        diagnoses.addProducts(List.of(Product.pending(
                productName, null, SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null)));
        return diagnosesRepository.save(diagnoses).getProducts().getFirst();
    }

    private Product saveProduct() {
        Diagnoses diagnoses = Diagnoses.pending(UUID.randomUUID());
        diagnoses.addProducts(List.of(Product.pending(
                "대나무 헬리콥터", null, SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null)));
        return diagnosesRepository.save(diagnoses).getProducts().getFirst();
    }

    private LawAmendment createLawAmendment() {
        return LawAmendment.builder()
                .lawName("어린이제품 안전 특별법 시행규칙")
                .documentId("012345")
                .toolName(ToolName.CHILDREN)
                .serialNumber("291321")
                .build();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
