package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
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
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
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

import java.time.LocalDateTime;
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
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";
    private static final String RUN_ID = "run-1";

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
    @DisplayName("본인의 상품을 단건 조회하면 해당 상품을 반환한다.")
    void getProduct_thenReturnProduct() {
        // given
        Product product = createDiagnoses(List.of("상품 A")).getProducts().getFirst();
        given(productRepository.findWithImagesByIdAndUserId(PRODUCT_ID, USER_ID)).willReturn(Optional.of(product));

        // when
        Product result = productService.getProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(result).isSameAs(product);
    }

    @Test
    @DisplayName("없는 상품이나 다른 사용자의 상품을 단건 조회하면 NOT_FOUND 예외가 발생한다.")
    void getProduct_withUnknownOrOthersProduct_thenThrowNotFound() {
        // given: 소유권이 조회 조건에 들어 있어 두 경우 모두 빈 결과다.
        given(productRepository.findWithImagesByIdAndUserId(PRODUCT_ID, USER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> productService.getProduct(USER_ID, PRODUCT_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
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
    @DisplayName("답변 대기 중인 상품을 삭제하면 남은 상품 기준으로 진단서 상태가 완료로 바뀐다.")
    void removeProduct_withAwaitingInputProduct_thenRefreshToCompleted() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));
        givenProcessingStatuses(diagnoses, ProcessingStatus.AWAITING_INPUT, ProcessingStatus.COMPLETED);
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
    }

    @Test
    @DisplayName("진행 중인 상품을 삭제하면 남은 상품 중 일부만 실패했어도 진단서 상태는 완료가 된다.")
    void removeProduct_withInProgressProduct_thenRefreshToCompleted() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B", "상품 C"));
        givenProcessingStatuses(diagnoses,
                ProcessingStatus.IN_PROGRESS, ProcessingStatus.COMPLETED, ProcessingStatus.FAILED);
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
    }

    @Test
    @DisplayName("완료된 상품을 삭제해 실패한 상품만 남으면 진단서 상태는 실패가 된다.")
    void removeProduct_withOnlyFailedRemaining_thenRefreshToFailed() {
        // given
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A", "상품 B"));
        givenProcessingStatuses(diagnoses, ProcessingStatus.COMPLETED, ProcessingStatus.FAILED);
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("마지막 상품을 삭제하면 빈 목록으로 상태를 다시 계산하지 않는다.")
    void removeProduct_withLastProduct_thenKeepProcessingStatus() {
        // given: 빈 목록으로 다시 계산하면 allMatch가 true라 FAILED가 된다.
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));
        givenProcessingStatuses(diagnoses, ProcessingStatus.AWAITING_INPUT);
        givenLockedDiagnoses(diagnoses);

        // when
        productService.removeProduct(USER_ID, PRODUCT_ID);

        // then
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
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

        then(diagnosesRepository).should(never()).findByIdAndUserIdForUpdate(any(), any());
    }

    @Test
    @DisplayName("락 조회 결과가 없으면(앞선 요청이 진단서를 삭제했거나 남의 진단서) NOT_FOUND 예외가 발생한다.")
    void removeProduct_whenDiagnosesDeletedWhileWaitingForLock_thenThrowNotFound() {
        // given: 마지막 상품을 연타한 경우. 앞선 요청이 상품과 함께 빈 진단서까지 지웠다.
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        given(diagnosesRepository.findByIdAndUserIdForUpdate(DIAGNOSES_ID, USER_ID)).willReturn(Optional.empty());

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
    @DisplayName("현재 실행의 결과를 받으면 상품이 완료되고 진단서 상태가 다시 계산된다.")
    void completeDiagnoses_thenCompleteProductAndRefreshDiagnoses() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, assessmentContent("구매대행으로 판매할 수 있습니다."));

        // then
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
        assertThat(product.getSummary()).isEqualTo("구매대행으로 판매할 수 있습니다.");
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.COMPLETED);
    }

    @Test
    @DisplayName("다른 상품이 아직 진행 중이면 결과를 반영해도 진단서는 진행 중으로 남는다.")
    void completeDiagnoses_withOtherProductInProgress_thenDiagnosesStillInProgress() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A", "상품 B"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, assessmentContent("결과"));

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus)
                .containsExactly(ProcessingStatus.COMPLETED, ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("실행 식별자를 저장하기 전에 결과가 오면 다시 보내 달라는 LOCK_CONFLICT 예외가 발생하고 결과를 반영하지 않는다.")
    void completeDiagnoses_whenRunNotAssigned_thenThrowLockConflict() {
        // given: AI의 202 응답을 저장하기 전에 결과 콜백이 먼저 도착한 경우
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));
        diagnoses.startDiagnoses();
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertThatThrownBy(() -> productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, assessmentContent("결과")))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.LOCK_CONFLICT);
        assertThat(diagnoses.getProducts().getFirst().getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("이전 실행의 결과가 늦게 오면 예외 없이 무시하고 상품은 진행 중으로 남는다.")
    void completeDiagnoses_withPreviousRun_thenIgnore() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, "previous-run", assessmentContent("지난 결과"));

        // then
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getSummary()).isNull();
    }

    @Test
    @DisplayName("이미 결과가 반영된 상품에 결과가 다시 오면 예외 없이 무시하고 기존 결과를 유지한다.")
    void completeDiagnoses_whenAlreadyCompleted_thenIgnore() {
        // given: AI가 같은 결과를 재전송한 경우
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);
        productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, assessmentContent("처음 받은 결과"));

        // when
        productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, assessmentContent("다시 받은 결과"));

        // then
        assertThat(diagnoses.getProducts().getFirst().getSummary()).isEqualTo("처음 받은 결과");
    }

    @Test
    @DisplayName("없는 진단서의 결과가 오면 NOT_FOUND 예외가 발생한다.")
    void completeDiagnoses_whenDiagnosesNotFound_thenThrowNotFound() {
        // given
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, assessmentContent("결과")))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("진단서에 속하지 않은 상품의 결과가 오면 NOT_FOUND 예외가 발생하고 아무것도 바뀌지 않는다.")
    void completeDiagnoses_whenProductNotInDiagnoses_thenThrowNotFound() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertThatThrownBy(() -> productService.completeDiagnoses(DIAGNOSES_ID, UUID.randomUUID(), RUN_ID, assessmentContent("결과")))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
        assertThat(diagnoses.getProducts().getFirst().getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("멈춘 상품 ID는 진행 중 상태와 기준 시각, 요청한 개수로 조회한다.")
    void findStuckProductIds_thenQueryInProgressWithLimit() {
        // given
        LocalDateTime threshold = LocalDateTime.now();
        given(productRepository.findIdsByStatusUpdatedBefore(
                ProcessingStatus.IN_PROGRESS, threshold, PageRequest.of(0, 100)))
                .willReturn(List.of(PRODUCT_ID));

        // when & then
        assertThat(productService.findStuckProductIds(threshold, 100)).containsExactly(PRODUCT_ID);
    }

    @Test
    @DisplayName("기준 시각보다 오래 멈춘 진단은 BE 실패 코드로 실패 처리하고 진단서 상태를 다시 계산한다.")
    void failStuckDiagnoses_whenStuck_thenFailAndRefreshDiagnoses() {
        // given
        LocalDateTime threshold = LocalDateTime.now();
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        ReflectionTestUtils.setField(product, "updatedAt", threshold.minusMinutes(1));
        givenStuckLookup(diagnoses);

        // when
        boolean failed = productService.failStuckDiagnoses(PRODUCT_ID, threshold);

        // then
        assertThat(failed).isTrue();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(product)
                .extracting(Product::getFailedStage, Product::getErrorCode,
                        Product::getErrorMessage, Product::getErrorRetryable)
                .containsExactly(null, ProductService.STUCK_ERROR_CODE, ProductService.STUCK_ERROR_MESSAGE,
                        ProductService.STUCK_ERROR_RETRYABLE);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("다른 상품이 아직 진행 중이면 멈춘 상품을 실패 처리해도 진단서는 진행 중으로 남는다.")
    void failStuckDiagnoses_withOtherProductInProgress_thenDiagnosesStillInProgress() {
        // given
        LocalDateTime threshold = LocalDateTime.now();
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A", "상품 B"));
        ReflectionTestUtils.setField(diagnoses.getProducts().getFirst(), "updatedAt", threshold.minusMinutes(1));
        givenStuckLookup(diagnoses);

        // when
        productService.failStuckDiagnoses(PRODUCT_ID, threshold);

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus)
                .containsExactly(ProcessingStatus.FAILED, ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @ParameterizedTest(name = "{0}")
    @EnumSource(value = ProcessingStatus.class, mode = EnumSource.Mode.EXCLUDE, names = "IN_PROGRESS")
    @DisplayName("ID를 조회한 뒤 콜백 등으로 상태가 바뀐 상품은 건너뛰고 상태를 바꾸지 않는다.")
    void failStuckDiagnoses_whenStatusChanged_thenSkip(ProcessingStatus status) {
        // given
        LocalDateTime threshold = LocalDateTime.now();
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        ReflectionTestUtils.setField(product, "updatedAt", threshold.minusMinutes(1));
        ReflectionTestUtils.setField(product, "processingStatus", status);
        givenStuckLookup(diagnoses);

        // when
        boolean failed = productService.failStuckDiagnoses(PRODUCT_ID, threshold);

        // then
        assertThat(failed).isFalse();
        assertThat(product.getProcessingStatus()).isEqualTo(status);
        assertThat(product.getErrorCode()).isNull();
    }

    @Test
    @DisplayName("ID를 조회한 뒤 상태가 다시 갱신돼 기준 시각보다 오래되지 않았으면 건너뛴다.")
    void failStuckDiagnoses_whenUpdatedSinceThreshold_thenSkip() {
        // given: 기준 시각과 같은 순간에 갱신된 경우도 아직 멈춘 것이 아니다.
        LocalDateTime threshold = LocalDateTime.now();
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        ReflectionTestUtils.setField(product, "updatedAt", threshold);
        givenStuckLookup(diagnoses);

        // when
        boolean failed = productService.failStuckDiagnoses(PRODUCT_ID, threshold);

        // then
        assertThat(failed).isFalse();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("ID를 조회한 뒤 상품이 삭제됐으면 진단서를 잠그지 않고 건너뛴다.")
    void failStuckDiagnoses_whenProductDeleted_thenSkipWithoutLock() {
        // given
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.empty());

        // when
        boolean failed = productService.failStuckDiagnoses(PRODUCT_ID, LocalDateTime.now());

        // then
        assertThat(failed).isFalse();
        then(diagnosesRepository).should(never()).findByIdForUpdate(any());
    }

    @Test
    @DisplayName("락을 기다리는 동안 진단서가 삭제됐으면 건너뛴다.")
    void failStuckDiagnoses_whenDiagnosesDeletedWhileWaitingForLock_thenSkip() {
        // given
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.empty());

        // when & then
        assertThat(productService.failStuckDiagnoses(PRODUCT_ID, LocalDateTime.now())).isFalse();
    }

    @Test
    @DisplayName("락을 기다리는 동안 상품만 삭제됐으면 건너뛰고 남은 상품은 그대로 둔다.")
    void failStuckDiagnoses_whenProductDeletedWhileWaitingForLock_thenSkip() {
        // given
        UUID deletedProductId = UUID.randomUUID();
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        given(productRepository.findDiagnosesIdById(deletedProductId)).willReturn(Optional.of(DIAGNOSES_ID));
        givenLockedDiagnosesById(diagnoses);

        // when
        boolean failed = productService.failStuckDiagnoses(deletedProductId, LocalDateTime.now());

        // then
        assertThat(failed).isFalse();
        assertThat(diagnoses.getProducts().getFirst().getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    private void givenStuckLookup(Diagnoses diagnoses) {
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        givenLockedDiagnosesById(diagnoses);
    }

    private void givenLockedDiagnosesById(Diagnoses diagnoses) {
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));
    }

    // 진단을 시작하고 AI의 202 응답으로 받은 실행 식별자까지 저장한 상태
    private Diagnoses createRunningDiagnoses(List<String> productNames) {
        Diagnoses diagnoses = createDiagnoses(productNames);
        diagnoses.startDiagnoses();
        diagnoses.getProducts().forEach(product -> product.assignRun(RUN_ID));
        return diagnoses;
    }

    private AssessmentContent assessmentContent(String summary) {
        return new AssessmentContent(AssessmentStatus.COMPLETED, ResultStatus.PURCHASING_AGENT_ALLOWED,
                summary, List.of(), List.of(), List.of());
    }

    private void givenLockedDiagnoses(Diagnoses diagnoses) {
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        given(diagnosesRepository.findByIdAndUserIdForUpdate(DIAGNOSES_ID, USER_ID)).willReturn(Optional.of(diagnoses));
    }

    private Diagnoses createDiagnoses(List<String> productNames) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
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

    // 상품 상태를 순서대로 지정하고, 진단서 상태도 그 기준으로 맞춰 둔다.
    // Product에 아직 상태 변경 메서드가 없어 리플렉션으로 넣는다.
    private void givenProcessingStatuses(Diagnoses diagnoses, ProcessingStatus... statuses) {
        List<Product> products = diagnoses.getProducts();
        for (int i = 0; i < statuses.length; i++) {
            ReflectionTestUtils.setField(products.get(i), "processingStatus", statuses[i]);
        }
        diagnoses.refreshProcessingStatus();
    }
}
