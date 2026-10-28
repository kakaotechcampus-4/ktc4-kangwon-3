package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
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

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import java.util.UUID;

@ExtendWith(MockitoExtension.class)
class DiagnosesServiceTest {

    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID DIAGNOSES_ID_2 = UUID.randomUUID();
    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID OTHER_USER_ID = UUID.randomUUID();
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
    @DisplayName("진단을 요청하면 진단서와 상품이 모두 진단 중(IN_PROGRESS)으로 저장되고 진단 결과는 비어 있다.")
    void createDiagnoses_thenSaveAsInProgress() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(DIAGNOSES_ID));

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(createCommand(List.of())));

        // then
        then(diagnosesRepository).should().save(diagnosesCaptor.capture());
        Diagnoses saved = diagnosesCaptor.getValue();

        assertThat(saved.getUserId()).isEqualTo(USER_ID);
        assertThat(saved.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(saved.getProducts()).hasSize(1);

        Product product = saved.getProducts().getFirst();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getResultStatus()).isNull();
        assertThat(product.getSummary()).isNull();
        assertThat(product.getProductName()).isEqualTo(PRODUCT_NAME);
    }

    @Test
    @DisplayName("상품을 여러 개 등록하면 요청한 순서대로 정렬 값이 부여되고 하나의 진단서로 묶인다.")
    void createDiagnoses_withMultipleProducts_thenAssignSortOrderByRequestOrder() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(DIAGNOSES_ID));

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
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(DIAGNOSES_ID));
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
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(DIAGNOSES_ID));

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
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(DIAGNOSES_ID));

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
        Diagnoses diagnoses = createDiagnoses(DIAGNOSES_ID);
        given(diagnosesRepository.findWithProductsById(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        Diagnoses result = diagnosesService.getDiagnoses(USER_ID, DIAGNOSES_ID);

        // then
        assertThat(result).isEqualTo(diagnoses);
    }

    @Test
    @DisplayName("존재하지 않는 진단서를 조회하면 NOT_FOUND 예외가 발생한다.")
    void getDiagnoses_withUnknownId_thenThrowNotFound() {
        // given
        given(diagnosesRepository.findWithProductsById(DIAGNOSES_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> diagnosesService.getDiagnoses(USER_ID, DIAGNOSES_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 NOT_FOUND 예외가 발생한다.")
    void getDiagnoses_withOtherUsersDiagnoses_thenThrowNotFound() {
        // given
        given(diagnosesRepository.findWithProductsById(DIAGNOSES_ID))
                .willReturn(Optional.of(createDiagnoses(DIAGNOSES_ID, OTHER_USER_ID, List.of())));

        // when & then
        assertThatThrownBy(() -> diagnosesService.getDiagnoses(USER_ID, DIAGNOSES_ID))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("회원 탈퇴 시 해당 사용자의 모든 진단서가 저장소에서 삭제된다.")
    void removeAllByUserId_thenDeleteAllDiagnosesOfUser() {
        // given
        Diagnoses first = createDiagnoses(DIAGNOSES_ID);
        Diagnoses second = createDiagnoses(DIAGNOSES_ID_2);
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
        Diagnoses first = createDiagnoses(DIAGNOSES_ID, List.of("product-detail/1/uuid_a1.jpg"));
        Diagnoses second = createDiagnoses(DIAGNOSES_ID_2);
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

    @Test
    @DisplayName("진단을 요청하면 저장된 상품들의 입력 정보로 AI 진단 요청 이벤트를 발행한다.")
    void createDiagnoses_thenPublishAiDiagnosesRequestedEvent() {
        // given: 저장할 때 id가 부여되는 것을 흉내 낸다.
        UUID productId = UUID.randomUUID();
        given(diagnosesRepository.save(any(Diagnoses.class))).willAnswer(invocation -> {
            Diagnoses diagnoses = invocation.getArgument(0);
            ReflectionTestUtils.setField(diagnoses, "id", DIAGNOSES_ID);
            ReflectionTestUtils.setField(diagnoses.getProducts().getFirst(), "id", productId);
            return diagnoses;
        });

        // when
        diagnosesService.createDiagnoses(USER_ID, List.of(new ProductCreateCommand(
                PRODUCT_NAME, PRODUCT_IMAGE_KEY, SourceType.TEXT_IMAGE, null, "상세 설명",
                List.of("product-detail/1/uuid_a1.jpg"))));

        // then
        ArgumentCaptor<AiDiagnosesRequestedEvent> captor = ArgumentCaptor.forClass(AiDiagnosesRequestedEvent.class);
        then(eventPublisher).should().publishEvent(captor.capture());
        assertThat(captor.getValue()).isEqualTo(new AiDiagnosesRequestedEvent(DIAGNOSES_ID, List.of(
                new AiDiagnosesRequestedEvent.ProductInput(productId, SourceType.TEXT_IMAGE, null, "상세 설명",
                        List.of(PRODUCT_IMAGE_KEY, "product-detail/1/uuid_a1.jpg")))));
    }

    @Test
    @DisplayName("AI 접수 응답의 실행 식별자를 진단서를 잠근 뒤 각 상품에 저장한다.")
    void assignRuns_thenAssignRunIdToEachProduct() {
        // given
        Diagnoses diagnoses = createInProgressDiagnoses(2);
        UUID first = diagnoses.getProducts().get(0).getId();
        UUID second = diagnoses.getProducts().get(1).getId();
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.assignRuns(DIAGNOSES_ID, Map.of(first, "run-1", second, "run-2"));

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getRunId)
                .containsExactly("run-1", "run-2");
    }

    @Test
    @DisplayName("진단서에 없는 상품의 실행 식별자는 건너뛰고 나머지 상품에는 저장한다.")
    void assignRuns_withUnknownProduct_thenSkipIt() {
        // given
        Diagnoses diagnoses = createInProgressDiagnoses(1);
        UUID productId = diagnoses.getProducts().getFirst().getId();
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.assignRuns(DIAGNOSES_ID, Map.of(productId, "run-1", UUID.randomUUID(), "run-x"));

        // then
        assertThat(diagnoses.getProducts().getFirst().getRunId()).isEqualTo("run-1");
    }

    @Test
    @DisplayName("없는 진단서의 실행 식별자를 저장하려 하면 NOT_FOUND 예외가 발생한다.")
    void assignRuns_whenDiagnosesNotFound_thenThrowNotFound() {
        // given
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> diagnosesService.assignRuns(DIAGNOSES_ID, Map.of(UUID.randomUUID(), "run-1")))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("AI가 요청을 받지 않은 상품들만 대기 상태로 되돌리고 진단서는 진행 중으로 유지한다.")
    void returnToPending_thenOnlyRequestedProductsPending() {
        // given
        Diagnoses diagnoses = createInProgressDiagnoses(3);
        List<Product> products = diagnoses.getProducts();
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.returnToPending(DIAGNOSES_ID, List.of(products.get(0).getId(), products.get(1).getId()));

        // then
        assertThat(products)
                .extracting(Product::getProcessingStatus)
                .containsExactly(ProcessingStatus.PENDING, ProcessingStatus.PENDING, ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("이미 실행 식별자를 받았거나 진행 중이 아닌 상품은 건너뛰고 나머지 상품만 대기로 되돌린다.")
    void returnToPending_whenRunAssignedOrNotInProgress_thenSkipIt() {
        // given
        Diagnoses diagnoses = createInProgressDiagnoses(3);
        List<Product> products = diagnoses.getProducts();
        products.get(0).assignRun("run-1");
        products.get(1).fail(null, "AI_PIPELINE_ERROR", "진단 중 오류가 발생했습니다.", true);
        List<UUID> productIds = products.stream().map(Product::getId).toList();
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.returnToPending(DIAGNOSES_ID, productIds);

        // then
        assertThat(products)
                .extracting(Product::getProcessingStatus)
                .containsExactly(ProcessingStatus.IN_PROGRESS, ProcessingStatus.FAILED, ProcessingStatus.PENDING);
    }

    @Test
    @DisplayName("AI가 거절한 상품들은 다시 진단해도 같은 결과라 재시도 불가 실패로 끝내고 진단서 상태를 다시 계산한다.")
    void failRejectedRequest_thenFailAsNotRetryable() {
        // given
        Diagnoses diagnoses = createInProgressDiagnoses(2);
        List<UUID> productIds = diagnoses.getProducts().stream().map(Product::getId).toList();
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.failRejectedRequest(DIAGNOSES_ID, productIds);

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus, Product::getErrorCode, Product::getErrorRetryable)
                .containsOnly(tuple(ProcessingStatus.FAILED, DiagnosesService.REQUEST_REJECTED_ERROR_CODE, false));
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("이미 실행 식별자를 받은 상품은 실패 처리하지 않는다.")
    void failRejectedRequest_whenRunAssigned_thenSkip() {
        // given
        Diagnoses diagnoses = createInProgressDiagnoses(1);
        Product product = diagnoses.getProducts().getFirst();
        product.assignRun("run-1");
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.failRejectedRequest(DIAGNOSES_ID, List.of(product.getId()));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("재요청하면 대기 상품만 진행 중으로 바꾸고 그 상품들의 AI 요청 내용을 돌려준다.")
    void restartPendingProducts_thenStartPendingAndReturnEvent() {
        // given
        LocalDateTime now = LocalDateTime.now();
        Diagnoses diagnoses = createInProgressDiagnoses(2);
        Product pending = diagnoses.getProducts().get(0);
        pending.returnToPending();
        diagnoses.getProducts().forEach(product -> ReflectionTestUtils.setField(product, "requestedAt", now));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        Optional<AiDiagnosesRequestedEvent> event =
                diagnosesService.restartPendingProducts(DIAGNOSES_ID, now.minusMinutes(10));

        // then
        assertThat(event).hasValueSatisfying(requested -> {
            assertThat(requested.diagnosesId()).isEqualTo(DIAGNOSES_ID);
            assertThat(requested.products())
                    .extracting(AiDiagnosesRequestedEvent.ProductInput::productId)
                    .containsExactly(pending.getId());
        });
        assertThat(pending.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("재요청 기한을 넘긴 대기 상품은 다시 보내지 않고 재시도 가능한 실패로 끝낸다.")
    void restartPendingProducts_whenPastDeadline_thenFailAsRetryable() {
        // given
        LocalDateTime now = LocalDateTime.now();
        Diagnoses diagnoses = createInProgressDiagnoses(2);
        Product expired = diagnoses.getProducts().get(0);
        Product waiting = diagnoses.getProducts().get(1);
        expired.returnToPending();
        waiting.returnToPending();
        ReflectionTestUtils.setField(expired, "requestedAt", now.minusMinutes(11));
        ReflectionTestUtils.setField(waiting, "requestedAt", now.minusMinutes(9));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        Optional<AiDiagnosesRequestedEvent> event =
                diagnosesService.restartPendingProducts(DIAGNOSES_ID, now.minusMinutes(10));

        // then
        assertThat(event).hasValueSatisfying(requested -> assertThat(requested.products())
                .extracting(AiDiagnosesRequestedEvent.ProductInput::productId)
                .containsExactly(waiting.getId()));
        assertThat(expired.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(expired.getErrorCode()).isEqualTo(DiagnosesService.REQUEST_UNAVAILABLE_ERROR_CODE);
        assertThat(expired.getErrorRetryable()).isTrue();
        assertThat(waiting.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("다시 보낼 대기 상품이 없으면 재요청하지 않는다.")
    void restartPendingProducts_whenNoPending_thenEmpty() {
        // given: 기한을 넘긴 상품뿐인 경우
        LocalDateTime now = LocalDateTime.now();
        Diagnoses diagnoses = createInProgressDiagnoses(1);
        Product expired = diagnoses.getProducts().getFirst();
        expired.returnToPending();
        ReflectionTestUtils.setField(expired, "requestedAt", now.minusMinutes(11));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        Optional<AiDiagnosesRequestedEvent> event =
                diagnosesService.restartPendingProducts(DIAGNOSES_ID, now.minusMinutes(10));

        // then
        assertThat(event).isEmpty();
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("오래전에 만든 상품이라도 최근에 다시 요청했으면 기한 안으로 보고 재요청한다.")
    void restartPendingProducts_whenCreatedLongAgoButRequestedRecently_thenRestart() {
        // given: 하루 전에 만들었지만 방금 다시 진단을 요청한 상품
        LocalDateTime now = LocalDateTime.now();
        Diagnoses diagnoses = createInProgressDiagnoses(1);
        Product product = diagnoses.getProducts().getFirst();
        product.returnToPending();
        ReflectionTestUtils.setField(product, "createdAt", now.minusDays(1));
        ReflectionTestUtils.setField(product, "requestedAt", now.minusMinutes(1));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        Optional<AiDiagnosesRequestedEvent> event =
                diagnosesService.restartPendingProducts(DIAGNOSES_ID, now.minusMinutes(10));

        // then
        assertThat(event).hasValueSatisfying(requested -> assertThat(requested.products())
                .extracting(AiDiagnosesRequestedEvent.ProductInput::productId)
                .containsExactly(product.getId()));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("요청 시각이 없는 기존 상품은 생성 시각을 기준으로 기한을 판단한다.")
    void restartPendingProducts_whenRequestedAtIsNull_thenUseCreatedAt() {
        // given: requested_at 컬럼 추가 전에 만들어진 상품
        LocalDateTime now = LocalDateTime.now();
        Diagnoses diagnoses = createInProgressDiagnoses(1);
        Product expired = diagnoses.getProducts().getFirst();
        expired.returnToPending();
        ReflectionTestUtils.setField(expired, "requestedAt", null);
        ReflectionTestUtils.setField(expired, "createdAt", now.minusMinutes(11));
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.of(diagnoses));

        // when
        Optional<AiDiagnosesRequestedEvent> event =
                diagnosesService.restartPendingProducts(DIAGNOSES_ID, now.minusMinutes(10));

        // then
        assertThat(event).isEmpty();
        assertThat(expired.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(expired.getErrorCode()).isEqualTo(DiagnosesService.REQUEST_UNAVAILABLE_ERROR_CODE);
    }

    @Test
    @DisplayName("재요청하려던 진단서가 그 사이 삭제됐으면 재요청하지 않는다.")
    void restartPendingProducts_whenDiagnosesDeleted_thenEmpty() {
        // given
        given(diagnosesRepository.findByIdForUpdate(DIAGNOSES_ID)).willReturn(Optional.empty());

        // when
        Optional<AiDiagnosesRequestedEvent> event =
                diagnosesService.restartPendingProducts(DIAGNOSES_ID, LocalDateTime.now());

        // then
        assertThat(event).isEmpty();
    }

    // 진단을 시작한 상품 n개를 가진 진단서. 상품마다 id를 부여한다.
    private Diagnoses createInProgressDiagnoses(int productCount) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        ReflectionTestUtils.setField(diagnoses, "id", DIAGNOSES_ID);
        for (int i = 0; i < productCount; i++) {
            Product product = Product.pending(PRODUCT_NAME + i, null, SourceType.URL, SOURCE_URL, null);
            ReflectionTestUtils.setField(product, "id", UUID.randomUUID());
            diagnoses.addProducts(List.of(product));
        }
        diagnoses.startDiagnoses();
        return diagnoses;
    }

    private Diagnoses createDiagnoses(UUID diagnosesId) {
        return createDiagnoses(diagnosesId, List.of());
    }

    private Diagnoses createDiagnoses(UUID diagnosesId, List<String> imageKeys) {
        return createDiagnoses(diagnosesId, USER_ID, imageKeys);
    }

    private Diagnoses createDiagnoses(UUID diagnosesId, UUID ownerId, List<String> imageKeys) {
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
