package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class DiagnosesServiceTest {

    private static final Long USER_ID = 1L;
    private static final Long OTHER_USER_ID = 2L;
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Mock
    private DiagnosesRepository diagnosesRepository;

    @Mock
    private S3FileService s3FileService;

    @Mock
    private ApplicationEventPublisher eventPublisher;

    @InjectMocks
    private DiagnosesService diagnosesService;

    @Captor
    private ArgumentCaptor<Diagnoses> diagnosesCaptor;

    @Captor
    private ArgumentCaptor<S3FileDeleteRequestedEvent> eventCaptor;

    @Test
    @DisplayName("진단을 요청하면 진단서와 상품이 모두 PENDING 상태로 저장되고 진단 결과는 비어 있다.")
    void createDiagnoses_thenSaveAsPending() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L));

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(createCommand(List.of())));

        // then
        then(diagnosesRepository).should().save(diagnosesCaptor.capture());
        Diagnoses saved = diagnosesCaptor.getValue();

        assertThat(saved.getUserId()).isEqualTo(USER_ID);
        assertThat(saved.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(saved.getProducts()).hasSize(1);

        Product product = saved.getProducts().getFirst();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(product.getResultStatus()).isNull();
        assertThat(product.getSummary()).isNull();
        assertThat(product.getProductName()).isEqualTo(PRODUCT_NAME);
    }

    @Test
    @DisplayName("상품을 여러 개 등록하면 요청한 순서대로 정렬 값이 부여되고 하나의 진단서로 묶인다.")
    void createDiagnoses_withMultipleProducts_thenAssignSortOrderByRequestOrder() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L));

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(
                createCommand("상품 A", List.of()),
                createCommand("상품 B", List.of()),
                createCommand("상품 C", List.of())));

        // then
        then(diagnosesRepository).should().save(diagnosesCaptor.capture());

        assertThat(diagnosesCaptor.getValue().getProducts())
                .extracting(Product::getProductName, Product::getSortOrder)
                .containsExactly(
                        tuple("상품 A", 0),
                        tuple("상품 B", 1),
                        tuple("상품 C", 2));
    }

    @Test
    @DisplayName("상품에 이미지를 여러 장 등록하면 업로드한 순서대로 정렬 값이 부여된다.")
    void createDiagnoses_withImages_thenAssignSortOrderByUploadOrder() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L));
        List<String> imageKeys = List.of(
                "product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg", "product-detail/1/uuid_a3.jpg");

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(createCommand(imageKeys)));

        // then
        then(diagnosesRepository).should().save(diagnosesCaptor.capture());

        assertThat(diagnosesCaptor.getValue().getProducts().getFirst().getImages())
                .extracting(ProductImage::getImageKey, ProductImage::getSortOrder)
                .containsExactly(
                        tuple("product-detail/1/uuid_a1.jpg", 0),
                        tuple("product-detail/1/uuid_a2.jpg", 1),
                        tuple("product-detail/1/uuid_a3.jpg", 2));
    }

    @Test
    @DisplayName("진단서를 생성하면 모든 상품의 대표 이미지와 첨부 이미지 key가 CONFIRMED로 전환된다.")
    void createDiagnoses_thenMarkImageKeysOfAllProductsAsConfirmed() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L));

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(
                createCommand(List.of("product-detail/1/uuid_a1.jpg")),
                createCommand(List.of("product-detail/1/uuid_b1.jpg"))));

        // then
        then(s3FileService).should().markConfirmed(List.of(
                PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg",
                PRODUCT_IMAGE_KEY, "product-detail/1/uuid_b1.jpg"));
    }

    @Test
    @DisplayName("이미지 없이 진단을 요청하면 상품만 저장된다.")
    void createDiagnoses_withoutImages_thenSaveProductOnly() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L));

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(createCommand(List.of())));

        // then
        then(diagnosesRepository).should().save(diagnosesCaptor.capture());
        assertThat(diagnosesCaptor.getValue().getProducts().getFirst().getImages()).isEmpty();
    }

    @Test
    @DisplayName("본인의 진단서를 조회하면 해당 진단서를 반환한다.")
    void getDiagnoses_thenReturnDiagnoses() {
        // given
        Diagnoses diagnoses = createDiagnoses(1L);
        given(diagnosesRepository.findWithProductsById(1L)).willReturn(Optional.of(diagnoses));

        // when
        Diagnoses result = diagnosesService.getDiagnoses(USER_ID, 1L);

        // then
        assertThat(result).isEqualTo(diagnoses);
    }

    @Test
    @DisplayName("존재하지 않는 진단서를 조회하면 NOT_FOUND 예외가 발생한다.")
    void getDiagnoses_withUnknownId_thenThrowNotFound() {
        // given
        given(diagnosesRepository.findWithProductsById(1L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> diagnosesService.getDiagnoses(USER_ID, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 FORBIDDEN 예외가 발생한다.")
    void getDiagnoses_withOtherUsersDiagnoses_thenThrowForbidden() {
        // given
        given(diagnosesRepository.findWithProductsById(1L))
                .willReturn(Optional.of(createDiagnoses(1L, OTHER_USER_ID, List.of())));

        // when & then
        assertThatThrownBy(() -> diagnosesService.getDiagnoses(USER_ID, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.FORBIDDEN);
    }

    @Test
    @DisplayName("회원 탈퇴 시 해당 사용자의 모든 진단서가 저장소에서 삭제된다.")
    void removeAllByUserId_thenDeleteAllDiagnosesOfUser() {
        // given
        Diagnoses first = createDiagnoses(1L);
        Diagnoses second = createDiagnoses(2L);
        given(diagnosesRepository.findWithProductsByUserId(USER_ID)).willReturn(List.of(first, second));

        // when
        diagnosesService.removeAllByUserId(USER_ID);

        // then
        then(diagnosesRepository).should().deleteAll(List.of(first, second));
    }

    @Test
    @DisplayName("회원 탈퇴 시 모든 진단서에 속한 상품 이미지 key에 대해 S3 삭제 이벤트가 한 번에 발행된다.")
    void removeAllByUserId_thenPublishS3FileDeleteEventForAllDiagnoses() {
        // given
        Diagnoses first = createDiagnoses(1L, List.of("product-detail/1/uuid_a1.jpg"));
        Diagnoses second = createDiagnoses(2L);
        given(diagnosesRepository.findWithProductsByUserId(USER_ID)).willReturn(List.of(first, second));

        // when
        diagnosesService.removeAllByUserId(USER_ID);

        // then
        then(eventPublisher).should().publishEvent(eventCaptor.capture());
        assertThat(eventCaptor.getValue().keys())
                .containsExactly(PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg", PRODUCT_IMAGE_KEY);
    }

    @Test
    @DisplayName("회원 탈퇴 시 삭제할 진단서가 없으면 이벤트를 발행하지 않는다.")
    void removeAllByUserId_withNoDiagnoses_thenDoNotPublishEvent() {
        // given
        given(diagnosesRepository.findWithProductsByUserId(USER_ID)).willReturn(List.of());

        // when
        diagnosesService.removeAllByUserId(USER_ID);

        // then
        then(eventPublisher).should(never()).publishEvent(any());
    }

    private Diagnoses createDiagnoses(Long diagnosesId) {
        return createDiagnoses(diagnosesId, List.of());
    }

    private Diagnoses createDiagnoses(Long diagnosesId, List<String> imageKeys) {
        return createDiagnoses(diagnosesId, USER_ID, imageKeys);
    }

    private Diagnoses createDiagnoses(Long diagnosesId, Long ownerId, List<String> imageKeys) {
        Diagnoses diagnoses = Diagnoses.pending(ownerId);
        ReflectionTestUtils.setField(diagnoses, "id", diagnosesId);

        Product product = Product.pending(
                PRODUCT_NAME, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null);
        product.addImages(imageKeys);
        diagnoses.addProducts(List.of(product));

        return diagnoses;
    }

    private ProductCreateCommand createCommand(List<String> imageKeys) {
        return createCommand(PRODUCT_NAME, imageKeys);
    }

    private ProductCreateCommand createCommand(String productName, List<String> imageKeys) {
        return new ProductCreateCommand(
                productName, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null, imageKeys);
    }
}
