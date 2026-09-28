package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
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
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import java.util.UUID;

@ExtendWith(MockitoExtension.class)
class ProductServiceTest {

    private static final UUID PRODUCT_ID = UUID.randomUUID();
    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID OTHER_USER_ID = UUID.randomUUID();
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Mock
    private ProductRepository productRepository;

    @Mock
    private DiagnosesRepository diagnosesRepository;

    @Mock
    private ApplicationEventPublisher eventPublisher;

    @InjectMocks
    private ProductService productService;

    @Captor
    private ArgumentCaptor<S3FileDeleteRequestedEvent> eventCaptor;

    @Test
    @DisplayName("필터 없이 목록을 조회하면 결과 상태와 검색어가 비어 있는 채로 조회한다.")
    void getProductList_withoutFilter_thenSearchWithNulls() {
        // given
        Pageable pageable = PageRequest.of(0, 10);
        given(productRepository.search(eq(USER_ID), isNull(), isNull(), eq(pageable))).willReturn(Page.empty());

        // when
        productService.getProductList(USER_ID, null, null, pageable);

        // then
        then(productRepository).should().search(USER_ID, null, null, pageable);
    }

    @Test
    @DisplayName("결과 필터와 검색어를 지정해 목록을 조회하면 그대로 전달된다.")
    void getProductList_withFilterAndKeyword_thenPassBoth() {
        // given
        Pageable pageable = PageRequest.of(0, 10);
        given(productRepository.search(any(), any(), any(), any())).willReturn(Page.empty());

        // when
        productService.getProductList(USER_ID, ResultStatus.RECHECK_REQUIRED, "헬리콥터", pageable);

        // then
        then(productRepository).should()
                .search(USER_ID, ResultStatus.RECHECK_REQUIRED, "헬리콥터", pageable);
    }

    @Test
    @DisplayName("검색어가 공백뿐이면 검색하지 않은 것으로 취급한다.")
    void getProductList_withBlankKeyword_thenTreatAsNoKeyword() {
        // given
        Pageable pageable = PageRequest.of(0, 10);
        given(productRepository.search(any(), any(), any(), any())).willReturn(Page.empty());

        // when
        productService.getProductList(USER_ID, null, "   ", pageable);

        // then
        then(productRepository).should().search(USER_ID, null, null, pageable);
    }

    @Test
    @DisplayName("검색어 앞뒤 공백은 제거된다.")
    void getProductList_withPaddedKeyword_thenTrim() {
        // given
        Pageable pageable = PageRequest.of(0, 10);
        given(productRepository.search(any(), any(), any(), any())).willReturn(Page.empty());

        // when
        productService.getProductList(USER_ID, null, "  헬리콥터  ", pageable);

        // then
        then(productRepository).should().search(USER_ID, null, "헬리콥터", pageable);
    }

    @Test
    @DisplayName("본인의 상품을 삭제하면 진단서에서 제거된다.")
    void removeProduct_thenRemoveFromDiagnoses() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProductName)
                .containsExactly("상품 B");
    }

    @Test
    @DisplayName("상품을 삭제하면 대표 이미지와 상세 이미지 key의 S3 삭제 이벤트가 발행된다.")
    void removeProduct_thenPublishS3FileDeleteEvent() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));
        diagnoses.getProducts().getFirst().addImages(List.of("product-detail/1/uuid_a1.jpg"));
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        then(eventPublisher).should().publishEvent(eventCaptor.capture());
        assertThat(eventCaptor.getValue().keys())
                .containsExactly(PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg");
    }

    @Test
    @DisplayName("상품이 남아 있으면 진단서는 삭제되지 않는다.")
    void removeProduct_withRemainingProducts_thenKeepDiagnoses() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        then(diagnosesRepository).should(never()).delete(any());
    }

    @Test
    @DisplayName("마지막 상품을 삭제하면 빈 진단서도 함께 삭제된다.")
    void removeProduct_withLastProduct_thenDeleteDiagnoses() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(diagnoses.getProducts()).isEmpty();
        then(diagnosesRepository).should().delete(diagnoses);
    }

    @Test
    @DisplayName("존재하지 않는 상품을 삭제하면 진단서를 잠그지 않고 NOT_FOUND 예외가 발생한다.")
    void removeProduct_withUnknownId_thenThrowNotFound() {
        // given
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> productService.removeProduct(USER_ID, PRODUCT_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);

        then(diagnosesRepository).should(never()).findByIdForUpdate(any());
    }

    @Test
    @DisplayName("락을 기다리는 사이 앞선 요청이 진단서까지 삭제했다면 NOT_FOUND 예외가 발생한다.")
    void removeProduct_whenDiagnosesDeletedWhileWaitingForLock_thenThrowNotFound() {
        // given: 마지막 상품을 연타한 경우. 앞선 요청이 상품과 함께 빈 진단서까지 지웠다.
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> productService.removeProduct(USER_ID, PRODUCT_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);

        then(eventPublisher).should(never()).publishEvent(any());
    }

    @Test
    @DisplayName("락을 얻은 뒤 보니 상품이 이미 삭제되었다면 NOT_FOUND 예외가 발생하고 아무것도 삭제되지 않는다.")
    void removeProduct_whenProductDeletedWhileWaitingForLock_thenThrowNotFound() {
        // given: 같은 상품을 연타한 경우. 앞선 요청이 대상 상품만 지워 목록에는 다른 상품만 남아 있다.
        Diagnoses diagnoses = createDiagnoses(List.of("상품 B"));
        ReflectionTestUtils.setField(diagnoses.getProducts().getFirst(), "id", UUID.randomUUID());
        givenLockedDiagnoses(diagnoses);

        // when & then
        assertThatThrownBy(() -> productService.removeProduct(USER_ID, PRODUCT_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);

        assertThat(diagnoses.getProducts()).hasSize(1);
        then(diagnosesRepository).should(never()).delete(any());
        then(eventPublisher).should(never()).publishEvent(any());
    }

    @Test
    @DisplayName("다른 사용자의 상품을 삭제하려 하면 NOT_FOUND 예외가 발생하고 아무것도 삭제되지 않는다.")
    void removeProduct_withOtherUsersProduct_thenThrowNotFound() {
        // given
        Diagnoses diagnoses = createDiagnoses(OTHER_USER_ID, List.of("상품 A"));
        givenLockedDiagnoses(diagnoses);

        // when & then
        assertThatThrownBy(() -> productService.removeProduct(USER_ID, PRODUCT_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);

        assertThat(diagnoses.getProducts()).hasSize(1);
        then(diagnosesRepository).should(never()).delete(any());
        then(eventPublisher).should(never()).publishEvent(any());
    }

    private void givenLockedDiagnoses(Diagnoses diagnoses) {
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));
    }

    private Diagnoses createDiagnoses(List<String> productNames) {
        return createDiagnoses(USER_ID, productNames);
    }

    private Diagnoses createDiagnoses(UUID ownerId, List<String> productNames) {
        Diagnoses diagnoses = Diagnoses.pending(ownerId);
        ReflectionTestUtils.setField(diagnoses, "id", DIAGNOSES_ID);

        diagnoses.addProducts(productNames.stream()
                .map(name -> Product.pending(name, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null))
                .toList());

        // 서비스가 락을 얻은 뒤 목록에서 productId 로 대상을 찾으므로 id 가 있어야 한다.
        // 첫 번째 상품을 삭제 대상(PRODUCT_ID)으로 두고, 나머지는 임의 id 를 준다.
        List<Product> products = diagnoses.getProducts();
        for (int i = 0; i < products.size(); i++) {
            ReflectionTestUtils.setField(products.get(i), "id", i == 0 ? PRODUCT_ID : UUID.randomUUID());
        }

        return diagnoses;
    }
}
