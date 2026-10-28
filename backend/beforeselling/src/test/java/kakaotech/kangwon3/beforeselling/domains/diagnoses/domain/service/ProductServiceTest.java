package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.AssessmentStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.PipelineStage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductProgress;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProductQuestion;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.QuestionContent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.StageStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import org.assertj.core.api.ThrowableAssert.ThrowingCallable;
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
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
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
    @DisplayName("질문에 답하면 상품과 진단서가 다시 진행 중 상태가 된다.")
    void answerQuestions_thenProductAndDiagnosesInProgress() {
        // given
        Diagnoses diagnoses = createAwaitingInputDiagnoses();
        givenLockedDiagnoses(diagnoses);
        Product product = diagnoses.getProducts().getFirst();

        // when
        productService.answerQuestions(USER_ID, PRODUCT_ID, answersOf(product, "구매대행", "네"));

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("질문에 답하면 질문으로 끝난 실행 ID와 회차, 질문 키별 답변을 담은 재진단 요청 이벤트를 발행한다.")
    void answerQuestions_thenPublishResumeEvent() {
        // given
        Diagnoses diagnoses = createAwaitingInputDiagnoses();
        givenLockedDiagnoses(diagnoses);
        Product product = diagnoses.getProducts().getFirst();

        // when
        productService.answerQuestions(USER_ID, PRODUCT_ID, answersOf(product, "구매대행", "네"));

        // then
        ArgumentCaptor<AiResumeRequestedEvent> captor = ArgumentCaptor.forClass(AiResumeRequestedEvent.class);
        then(eventPublisher).should().publishEvent(captor.capture());
        assertThat(captor.getValue()).isEqualTo(new AiResumeRequestedEvent(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1, List.of(
                new AiResumeRequestedEvent.Answer("sales_type", "구매대행"),
                new AiResumeRequestedEvent.Answer("battery_only", "네"))));
    }

    @Test
    @DisplayName("답변이 거절되면 재진단 요청 이벤트를 발행하지 않는다.")
    void answerQuestions_whenRejected_thenNotPublishEvent() {
        // given
        Diagnoses diagnoses = createAwaitingInputDiagnoses();
        givenLockedDiagnoses(diagnoses);
        Product product = diagnoses.getProducts().getFirst();
        Map<UUID, String> partialAnswers = Map.of(product.getQuestions().getFirst().getId(), "구매대행");

        // when & then
        assertResponseCode(() -> productService.answerQuestions(USER_ID, PRODUCT_ID, partialAnswers),
                CommonResponseCode.BAD_REQUEST);
        then(eventPublisher).should(never()).publishEvent(any());
    }

    @Test
    @DisplayName("존재하지 않는 상품에 답하면 진단서를 잠그지 않고 NOT_FOUND 예외가 발생한다.")
    void answerQuestions_withUnknownId_thenThrowNotFound() {
        // given
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.empty());

        // when & then
        assertResponseCode(() -> productService.answerQuestions(USER_ID, PRODUCT_ID, Map.of()),
                CommonResponseCode.NOT_FOUND);
        then(diagnosesRepository).should(never()).findByIdAndUserIdForUpdate(any(), any());
    }

    @Test
    @DisplayName("남의 상품에 답하면 락 조회 결과가 없어 NOT_FOUND 예외가 발생한다.")
    void answerQuestions_withOthersProduct_thenThrowNotFound() {
        // given
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.of(DIAGNOSES_ID));
        given(diagnosesRepository.findByIdAndUserIdForUpdate(DIAGNOSES_ID, USER_ID)).willReturn(Optional.empty());

        // when & then
        assertResponseCode(() -> productService.answerQuestions(USER_ID, PRODUCT_ID, Map.of()),
                CommonResponseCode.NOT_FOUND);
        then(eventPublisher).should(never()).publishEvent(any());
    }

    @Test
    @DisplayName("실패한 상품을 재시도하면 상품과 진단서가 다시 진행 중 상태가 된다.")
    void retryDiagnoses_thenProductAndDiagnosesInProgress() {
        // given: 상품 A는 실패, 상품 B는 완료라 진단서는 끝난 상태
        Diagnoses diagnoses = createFailedAndCompletedDiagnoses();
        givenLockedDiagnoses(diagnoses);
        Product product = diagnoses.getProducts().getFirst();

        // when
        productService.retryDiagnoses(USER_ID, PRODUCT_ID);

        // then
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("실패한 상품을 재시도하면 그 상품만 담은 AI 진단 요청 이벤트를 발행한다.")
    void retryDiagnoses_thenPublishRequestEventOfProduct() {
        // given
        Diagnoses diagnoses = createFailedAndCompletedDiagnoses();
        givenLockedDiagnoses(diagnoses);

        // when
        productService.retryDiagnoses(USER_ID, PRODUCT_ID);

        // then
        ArgumentCaptor<AiDiagnosesRequestedEvent> captor = ArgumentCaptor.forClass(AiDiagnosesRequestedEvent.class);
        then(eventPublisher).should().publishEvent(captor.capture());
        assertThat(captor.getValue().diagnosesId()).isEqualTo(DIAGNOSES_ID);
        assertThat(captor.getValue().products())
                .extracting(AiDiagnosesRequestedEvent.ProductInput::productId)
                .containsExactly(PRODUCT_ID);
    }

    @Test
    @DisplayName("재시도할 수 없는 상품이면 CONFLICT 예외가 발생하고 이벤트를 발행하지 않는다.")
    void retryDiagnoses_whenNotRetryable_thenThrowConflict() {
        // given: 진행 중인 상품
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnoses(diagnoses);

        // when & then
        assertResponseCode(() -> productService.retryDiagnoses(USER_ID, PRODUCT_ID), CommonResponseCode.CONFLICT);
        then(eventPublisher).should(never()).publishEvent(any());
    }

    @Test
    @DisplayName("존재하지 않는 상품을 재시도하면 진단서를 잠그지 않고 NOT_FOUND 예외가 발생한다.")
    void retryDiagnoses_withUnknownId_thenThrowNotFound() {
        // given
        given(productRepository.findDiagnosesIdById(PRODUCT_ID)).willReturn(Optional.empty());

        // when & then
        assertResponseCode(() -> productService.retryDiagnoses(USER_ID, PRODUCT_ID), CommonResponseCode.NOT_FOUND);
        then(diagnosesRepository).should(never()).findByIdAndUserIdForUpdate(any(), any());
    }

    @Test
    @DisplayName("현재 실행의 진행 상태를 받으면 단계·툴별 진행 상태가 저장되고 처리 상태는 그대로다.")
    void recordProgress_thenAddProgressAndKeepStatus() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.recordProgress(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 3,
                PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.CHILDREN);

        // then
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getProgresses())
                .extracting(ProductProgress::getRunId, ProductProgress::getSequence, ProductProgress::getStage,
                        ProductProgress::getStageStatus, ProductProgress::getToolName)
                .containsExactly(tuple(RUN_ID, 3, PipelineStage.TOOL_EXECUTION, StageStatus.STARTED, ToolName.CHILDREN));
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("실행 식별자를 저장하기 전에 진행 상태가 오면 다시 보내 달라는 LOCK_CONFLICT 예외가 발생하고 저장하지 않는다.")
    void recordProgress_whenRunNotAssigned_thenThrowLockConflict() {
        // given: AI의 202 응답을 저장하기 전에 진행 콜백이 먼저 도착한 경우
        Diagnoses diagnoses = createDiagnoses(List.of("상품 A"));
        diagnoses.startDiagnoses();
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertResponseCode(() -> productService.recordProgress(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                PipelineStage.EXTRACTION, StageStatus.STARTED, null), CommonResponseCode.LOCK_CONFLICT);
        assertThat(diagnoses.getProducts().getFirst().getProgresses()).isEmpty();
    }

    @Test
    @DisplayName("현재 실행과 다른 실행의 진행 상태가 오면 다시 보내 달라는 LOCK_CONFLICT 예외가 발생하고 저장하지 않는다.")
    void recordProgress_withOtherRun_thenThrowLockConflict() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertResponseCode(() -> productService.recordProgress(DIAGNOSES_ID, PRODUCT_ID, "other-run", 1,
                PipelineStage.EXTRACTION, StageStatus.STARTED, null), CommonResponseCode.LOCK_CONFLICT);
        assertThat(diagnoses.getProducts().getFirst().getProgresses()).isEmpty();
    }

    @Test
    @DisplayName("멈춘 진단 정리로 이미 실패 처리된 상품에 진행 상태가 오면 예외 없이 무시한다.")
    void recordProgress_whenFailed_thenIgnore() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        failByScheduler(product);
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.recordProgress(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 5,
                PipelineStage.AGGREGATION, StageStatus.STARTED, null);

        // then
        assertThat(product.getProgresses()).isEmpty();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("답변 대기 중인 상품에 진행 상태가 오면 CONFLICT 예외가 발생하고 저장하지 않는다.")
    void recordProgress_whenAwaitingInput_thenThrowConflict() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        product.askQuestions(1, List.of(question("sales_type", "구매대행으로 파나요?")));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertResponseCode(() -> productService.recordProgress(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 5,
                PipelineStage.AGGREGATION, StageStatus.STARTED, null), CommonResponseCode.CONFLICT);
        assertThat(product.getProgresses()).isEmpty();
    }

    @Test
    @DisplayName("현재 실행의 질문을 받으면 질문이 저장되고, 다른 상품이 진행 중이어도 진단서는 답변 대기가 된다.")
    void askQuestions_thenAddQuestionsAndDiagnosesAwaitingInput() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A", "상품 B"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                List.of(question("sales_type", "구매대행으로 파나요?"), question("target_age", "대상 연령은?")));

        // then
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getQuestions())
                .extracting(ProductQuestion::getQuestionRound, ProductQuestion::getQuestionKey)
                .containsExactly(tuple(1, "sales_type"), tuple(1, "target_age"));
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus)
                .containsExactly(ProcessingStatus.AWAITING_INPUT, ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
    }

    @Test
    @DisplayName("답변 대기 중에 이미 저장한 회차의 질문이 다시 오면 예외 없이 무시하고 처음 받은 질문을 유지한다.")
    void askQuestions_whenSameRoundResent_thenIgnore() {
        // given: 저장은 됐지만 응답이 유실돼 AI가 같은 질문을 다시 보낸 경우
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);
        productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                List.of(question("sales_type", "처음 받은 질문")));

        // when
        productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                List.of(question("sales_type", "다시 받은 질문")));

        // then
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getQuestions())
                .extracting(ProductQuestion::getQuestionText)
                .containsExactly("처음 받은 질문");
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
    }

    @Test
    @DisplayName("답변 대기 중에 다른 회차의 질문이 오면 CONFLICT 예외가 발생하고 질문이 늘지 않는다.")
    void askQuestions_whenOtherRoundWhileAwaitingInput_thenThrowConflict() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);
        productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                List.of(question("sales_type", "구매대행으로 파나요?")));

        // when & then
        assertResponseCode(() -> productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 2,
                List.of(question("target_age", "대상 연령은?"))), CommonResponseCode.CONFLICT);
        assertThat(diagnoses.getProducts().getFirst().getQuestions()).hasSize(1);
    }

    @Test
    @DisplayName("재진단 중에 이미 받은 회차의 질문이 다시 오면 무시하지 않고 CONFLICT 예외가 발생한다.")
    void askQuestions_whenReceivedRoundAfterResume_thenThrowConflict() {
        // given: 사용자가 답하고 재진단을 시작한 뒤 지난 회차 질문이 늦게 온 경우
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);
        productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                List.of(question("sales_type", "구매대행으로 파나요?")));
        Product product = diagnoses.getProducts().getFirst();
        product.resume();

        // when & then
        assertResponseCode(() -> productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, 1,
                List.of(question("sales_type", "구매대행으로 파나요?"))), CommonResponseCode.CONFLICT);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getQuestions()).hasSize(1);
    }

    @Test
    @DisplayName("현재 실행과 다른 실행의 질문이 오면 다시 보내 달라는 LOCK_CONFLICT 예외가 발생하고 저장하지 않는다.")
    void askQuestions_withOtherRun_thenThrowLockConflict() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertResponseCode(() -> productService.askQuestions(DIAGNOSES_ID, PRODUCT_ID, "other-run", 1,
                List.of(question("sales_type", "구매대행으로 파나요?"))), CommonResponseCode.LOCK_CONFLICT);
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getQuestions()).isEmpty();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
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
    @DisplayName("현재 실행과 다른 실행의 결과가 오면 다시 보내 달라는 LOCK_CONFLICT 예외가 발생하고 결과를 반영하지 않는다.")
    void completeDiagnoses_withOtherRun_thenThrowLockConflict() {
        // given: 새 실행의 runId를 저장하기 전에 그 결과가 먼저 왔거나, 이전 실행의 결과가 늦게 온 경우
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertThatThrownBy(() -> productService.completeDiagnoses(DIAGNOSES_ID, PRODUCT_ID, "other-run", assessmentContent("다른 실행 결과")))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.LOCK_CONFLICT);
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
    @DisplayName("현재 실행의 실패를 받으면 상품이 실패 정보와 함께 실패 처리되고 진단서 상태가 다시 계산된다.")
    void failDiagnoses_thenFailProductAndRefreshDiagnoses() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, PipelineStage.TOOL_EXECUTION,
                "AI_PIPELINE_ERROR", "진단 중 오류가 발생했습니다.", false);

        // then
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
        assertThat(product.getFailedStage()).isEqualTo(PipelineStage.TOOL_EXECUTION);
        assertThat(product.getErrorCode()).isEqualTo("AI_PIPELINE_ERROR");
        assertThat(product.getErrorMessage()).isEqualTo("진단 중 오류가 발생했습니다.");
        assertThat(product.getErrorRetryable()).isFalse();
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.FAILED);
    }

    @Test
    @DisplayName("다른 상품이 아직 진행 중이면 실패를 반영해도 진단서는 진행 중으로 남는다.")
    void failDiagnoses_withOtherProductInProgress_thenDiagnosesStillInProgress() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A", "상품 B"));
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, null, "AI_TIMEOUT", "시간이 초과되었습니다.", true);

        // then
        assertThat(diagnoses.getProducts())
                .extracting(Product::getProcessingStatus)
                .containsExactly(ProcessingStatus.FAILED, ProcessingStatus.IN_PROGRESS);
        assertThat(diagnoses.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
    }

    @Test
    @DisplayName("멈춘 진단 정리로 이미 실패 처리된 상품에 실패가 오면 예외 없이 무시하고 먼저 기록된 실패 정보를 유지한다.")
    void failDiagnoses_whenAlreadyFailed_thenIgnoreAndKeepFirstFailure() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        failByScheduler(product);
        givenLockedDiagnosesById(diagnoses);

        // when
        productService.failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, PipelineStage.TOOL_EXECUTION,
                "AI_TIMEOUT", "시간이 초과되었습니다.", true);

        // then
        assertThat(product.getErrorCode()).isEqualTo(ProductService.STUCK_ERROR_CODE);
        assertThat(product.getFailedStage()).isNull();
    }

    @Test
    @DisplayName("현재 실행과 다른 실행의 실패가 오면 다시 보내 달라는 LOCK_CONFLICT 예외가 발생하고 실패 처리하지 않는다.")
    void failDiagnoses_withOtherRun_thenThrowLockConflict() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertResponseCode(() -> productService.failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, "other-run", null,
                "AI_PIPELINE_ERROR", "진단 중 오류가 발생했습니다.", false), CommonResponseCode.LOCK_CONFLICT);
        Product product = diagnoses.getProducts().getFirst();
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.IN_PROGRESS);
        assertThat(product.getErrorCode()).isNull();
    }

    @Test
    @DisplayName("답변 대기 중인 상품에 실패가 오면 CONFLICT 예외가 발생하고 실패 처리하지 않는다.")
    void failDiagnoses_whenAwaitingInput_thenThrowConflict() {
        // given
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A"));
        Product product = diagnoses.getProducts().getFirst();
        product.askQuestions(1, List.of(question("sales_type", "구매대행으로 파나요?")));
        givenLockedDiagnosesById(diagnoses);

        // when & then
        assertResponseCode(() -> productService.failDiagnoses(DIAGNOSES_ID, PRODUCT_ID, RUN_ID, null,
                "AI_PIPELINE_ERROR", "진단 중 오류가 발생했습니다.", false), CommonResponseCode.CONFLICT);
        assertThat(product.getProcessingStatus()).isEqualTo(ProcessingStatus.AWAITING_INPUT);
        assertThat(product.getErrorCode()).isNull();
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
    @DisplayName("재요청할 진단서 ID는 대기 상태와 요청한 개수로 조회한다.")
    void findPendingDiagnosesIds_thenQueryPendingWithLimit() {
        // given
        given(productRepository.findDiagnosesIdsByStatus(ProcessingStatus.PENDING, PageRequest.of(0, 100)))
                .willReturn(List.of(DIAGNOSES_ID));

        // when & then
        assertThat(productService.findPendingDiagnosesIds(100)).containsExactly(DIAGNOSES_ID);
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

    // 첫 번째 상품(PRODUCT_ID)은 재시도 가능한 실패, 두 번째 상품은 완료라 진단서는 끝난 상태
    private Diagnoses createFailedAndCompletedDiagnoses() {
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A", "상품 B"));
        failByScheduler(diagnoses.getProducts().get(0));
        diagnoses.getProducts().get(1).complete(assessmentContent("요약"));
        diagnoses.refreshProcessingStatus();
        return diagnoses;
    }

    // 첫 번째 상품(PRODUCT_ID)이 1회차 질문 2개를 받아 답변을 기다리는 상태. 저장하지 않으므로 질문 ID를 직접 넣는다.
    private Diagnoses createAwaitingInputDiagnoses() {
        Diagnoses diagnoses = createRunningDiagnoses(List.of("상품 A", "상품 B"));
        Product product = diagnoses.getProducts().getFirst();
        product.askQuestions(1, List.of(question("sales_type", "구매대행으로 파나요?"),
                new QuestionContent("battery_only", 2, "내장 배터리로만 동작하나요?", null)));
        product.getQuestions().forEach(question -> ReflectionTestUtils.setField(question, "id", UUID.randomUUID()));
        diagnoses.refreshProcessingStatus();
        return diagnoses;
    }

    // 질문 순서대로 답변을 짝짓는다.
    private Map<UUID, String> answersOf(Product product, String... answerTexts) {
        List<ProductQuestion> questions = product.getQuestions();
        Map<UUID, String> answers = new HashMap<>();
        for (int i = 0; i < answerTexts.length; i++) {
            answers.put(questions.get(i).getId(), answerTexts[i]);
        }
        return answers;
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

    // 멈춘 진단 정리(failStuckDiagnoses)가 먼저 실패 처리한 상태
    private void failByScheduler(Product product) {
        product.fail(null, ProductService.STUCK_ERROR_CODE, ProductService.STUCK_ERROR_MESSAGE,
                ProductService.STUCK_ERROR_RETRYABLE);
    }

    private QuestionContent question(String questionKey, String questionText) {
        return new QuestionContent(questionKey, 1, questionText, null);
    }

    private void assertResponseCode(ThrowingCallable action, CommonResponseCode responseCode) {
        assertThatThrownBy(action)
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(responseCode);
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
