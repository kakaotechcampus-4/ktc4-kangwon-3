package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
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
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
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
class ProductServiceTest {

    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Mock
    private ProductRepository productRepository;

    @Mock
    private S3FileService s3FileService;

    @Mock
    private ApplicationEventPublisher eventPublisher;

    @InjectMocks
    private ProductService productService;

    @Captor
    private ArgumentCaptor<Product> diagnosesCaptor;

    @Captor
    private ArgumentCaptor<S3FileDeleteRequestedEvent> eventCaptor;

    @Test
    @DisplayName("진단을 요청하면 진단서가 PENDING 상태로 저장되고 진단 결과는 비어 있다.")
    void createDiagnoses_thenSaveAsPending() {
        // given
        given(productRepository.save(any(Product.class))).willReturn(createDiagnoses(1L, 1L));

        // when
        productService.createProduct(createCommand(1L, List.of()));

        // then
        then(productRepository).should().save(diagnosesCaptor.capture());
        Product saved = diagnosesCaptor.getValue();

        assertThat(saved.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(saved.getResultStatus()).isNull();
        assertThat(saved.getSummary()).isNull();
        assertThat(saved.getProductName()).isEqualTo(PRODUCT_NAME);
    }

    @Test
    @DisplayName("이미지를 여러 장 등록하면 업로드한 순서대로 정렬 값이 부여된다.")
    void createDiagnoses_withImages_thenAssignSortOrderByUploadOrder() {
        // given
        given(productRepository.save(any(Product.class))).willReturn(createDiagnoses(1L, 1L));
        List<String> imageKeys = List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg", "product-detail/1/uuid_a3.jpg");

        // when
        productService.createProduct(createCommand(1L, imageKeys));

        // then
        then(productRepository).should().save(diagnosesCaptor.capture());

        assertThat(diagnosesCaptor.getValue().getImages())
                .extracting(ProductImage::getImageKey, ProductImage::getSortOrder)
                .containsExactly(
                        tuple("product-detail/1/uuid_a1.jpg", 0),
                        tuple("product-detail/1/uuid_a2.jpg", 1),
                        tuple("product-detail/1/uuid_a3.jpg", 2));
    }

    @Test
    @DisplayName("진단서를 생성하면 대표 이미지와 첨부 이미지의 key가 모두 CONFIRMED로 전환된다.")
    void createDiagnoses_thenMarkImageKeysAsConfirmed() {
        // given
        given(productRepository.save(any(Product.class))).willReturn(createDiagnoses(1L, 1L));
        List<String> imageKeys = List.of("product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg");

        // when
        productService.createProduct(createCommand(1L, imageKeys));

        // then
        then(s3FileService).should().markConfirmed(List.of(
                PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg", "product-detail/1/uuid_a2.jpg"));
    }

    @Test
    @DisplayName("이미지 없이 진단을 요청하면 진단서만 저장된다.")
    void createDiagnoses_withoutImages_thenSaveDiagnosesOnly() {
        // given
        given(productRepository.save(any(Product.class))).willReturn(createDiagnoses(1L, 1L));

        // when
        productService.createProduct(createCommand(1L, List.of()));

        // then
        then(productRepository).should().save(diagnosesCaptor.capture());
        assertThat(diagnosesCaptor.getValue().getImages()).isEmpty();
    }

    @Test
    @DisplayName("본인의 진단서를 조회하면 해당 진단서를 반환한다.")
    void getDiagnoses_thenReturnDiagnoses() {
        // given
        Product product = createDiagnoses(1L, 1L);
        given(productRepository.findWithImagesById(1L)).willReturn(Optional.of(product));

        // when
        Product result = productService.getProduct(1L, 1L);

        // then
        assertThat(result).isEqualTo(product);
    }

    @Test
    @DisplayName("존재하지 않는 진단서를 조회하면 NOT_FOUND 예외가 발생한다.")
    void getDiagnoses_withUnknownId_thenThrowNotFound() {
        // given
        given(productRepository.findWithImagesById(1L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> productService.getProduct(1L, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 FORBIDDEN 예외가 발생한다.")
    void getDiagnoses_withOtherUsersDiagnoses_thenThrowForbidden() {
        // given
        given(productRepository.findWithImagesById(1L)).willReturn(Optional.of(createDiagnoses(1L, 2L)));

        // when & then
        assertThatThrownBy(() -> productService.getProduct(1L, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.FORBIDDEN);
    }

    @Test
    @DisplayName("결과 필터 없이 목록을 조회하면 사용자의 전체 진단서를 조회한다.")
    void getDiagnosesList_withoutFilter_thenFindAllOfUser() {
        // given
        Pageable pageable = PageRequest.of(0, 10);

        // when
        productService.getProductList(1L, null, pageable);

        // then
        then(productRepository).should().findByUserId(1L, pageable);
        then(productRepository).should(never()).findByUserIdAndResultStatus(any(), any(), any());
    }

    @Test
    @DisplayName("결과 필터를 지정해 목록을 조회하면 해당 결과의 진단서만 조회한다.")
    void getDiagnosesList_withFilter_thenFindByResultStatus() {
        // given
        Pageable pageable = PageRequest.of(0, 10);

        // when
        productService.getProductList(1L, ResultStatus.RECHECK_REQUIRED, pageable);

        // then
        then(productRepository).should()
                .findByUserIdAndResultStatus(1L, ResultStatus.RECHECK_REQUIRED, pageable);
        then(productRepository).should(never()).findByUserId(any(), any());
    }

    @Test
    @DisplayName("본인의 진단서를 삭제하면 저장소에서 삭제된다.")
    void removeDiagnoses_thenDeleteDiagnoses() {
        // given
        Product product = createDiagnoses(1L, 1L);
        given(productRepository.findWithImagesById(1L)).willReturn(Optional.of(product));

        // when
        productService.removeProduct(1L, 1L);

        // then
        then(productRepository).should().delete(product);
    }

    @Test
    @DisplayName("진단서를 삭제하면 딸린 이미지 key들의 S3 삭제를 요청하는 이벤트가 발행된다.")
    void removeDiagnoses_thenPublishS3FileDeleteEvent() {
        // given
        Product product = createDiagnoses(1L, 1L);
        product.addImages(List.of("product-detail/1/uuid_a1.jpg"));
        given(productRepository.findWithImagesById(1L)).willReturn(Optional.of(product));

        // when
        productService.removeProduct(1L, 1L);

        // then
        then(eventPublisher).should().publishEvent(eventCaptor.capture());
        assertThat(eventCaptor.getValue().keys())
                .containsExactly(PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg");
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 삭제하면 FORBIDDEN 예외가 발생하고 아무것도 삭제되지 않는다.")
    void removeDiagnoses_withOtherUsersDiagnoses_thenThrowForbidden() {
        // given
        given(productRepository.findWithImagesById(1L)).willReturn(Optional.of(createDiagnoses(1L, 2L)));

        // when & then
        assertThatThrownBy(() -> productService.removeProduct(1L, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.FORBIDDEN);

        then(productRepository).should(never()).delete(any());
    }

    @Test
    @DisplayName("회원 탈퇴 시 해당 사용자의 모든 진단서가 저장소에서 삭제된다.")
    void removeAllByUserId_thenDeleteAllDiagnosesOfUser() {
        // given
        Product first = createDiagnoses(1L, 1L);
        Product second = createDiagnoses(2L, 1L);
        given(productRepository.findWithImagesByUserId(1L)).willReturn(List.of(first, second));

        // when
        productService.removeAllByUserId(1L);

        // then
        then(productRepository).should().deleteAll(List.of(first, second));
    }

    @Test
    @DisplayName("회원 탈퇴 시 해당 사용자의 모든 진단서 이미지 key에 대해 S3 삭제 이벤트가 한 번에 발행된다.")
    void removeAllByUserId_thenPublishS3FileDeleteEventForAllDiagnoses() {
        // given
        Product first = createDiagnoses(1L, 1L);
        first.addImages(List.of("product-detail/1/uuid_a1.jpg"));
        Product second = createDiagnoses(2L, 1L);
        given(productRepository.findWithImagesByUserId(1L)).willReturn(List.of(first, second));

        // when
        productService.removeAllByUserId(1L);

        // then
        then(eventPublisher).should().publishEvent(eventCaptor.capture());
        assertThat(eventCaptor.getValue().keys())
                .containsExactly(PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg", PRODUCT_IMAGE_KEY);
    }

    @Test
    @DisplayName("회원 탈퇴 시 삭제할 진단서가 없으면 이벤트를 발행하지 않는다.")
    void removeAllByUserId_withNoDiagnoses_thenDoNotPublishEvent() {
        // given
        given(productRepository.findWithImagesByUserId(1L)).willReturn(List.of());

        // when
        productService.removeAllByUserId(1L);

        // then
        then(eventPublisher).should(never()).publishEvent(any());
    }

    private Product createDiagnoses(Long diagnosesId, Long userId) {
        Product product = Product.pending(
                userId, PRODUCT_NAME, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null);
        ReflectionTestUtils.setField(product, "id", diagnosesId);
        return product;
    }

    private ProductCreateCommand createCommand(Long userId, List<String> imageKeys) {
        return new ProductCreateCommand(
                userId, PRODUCT_NAME, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null, imageKeys);
    }
}
