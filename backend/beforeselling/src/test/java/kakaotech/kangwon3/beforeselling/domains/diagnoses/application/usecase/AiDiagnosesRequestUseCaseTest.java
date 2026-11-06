package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesRequestException;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesRequestException.Failure;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;

@ExtendWith(MockitoExtension.class)
class AiDiagnosesRequestUseCaseTest {

    private static final UUID DIAGNOSES_ID = UUID.randomUUID();
    private static final UUID TEXT_IMAGE_PRODUCT_ID = UUID.randomUUID();
    private static final UUID URL_PRODUCT_ID = UUID.randomUUID();
    private static final String S3_URL_PREFIX = "https://bucket.s3.ap-northeast-2.amazonaws.com/";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Mock
    private AiDiagnosesClient aiDiagnosesClient;

    @Mock
    private S3UrlKeyCodec s3UrlKeyCodec;

    @Mock
    private DiagnosesService diagnosesService;

    @InjectMocks
    private AiDiagnosesRequestUseCase aiDiagnosesRequestUseCase;

    @BeforeEach
    void setUp() {
        lenient().when(s3UrlKeyCodec.toUrl(anyString())).thenAnswer(invocation -> S3_URL_PREFIX + invocation.getArgument(0));
    }

    @Test
    @DisplayName("텍스트·이미지 상품은 텍스트와 이미지 URL로, URL만 있는 상품은 상세페이지 URL로 AI에 진단을 요청한다.")
    void requestDiagnoses_thenRequestBySourceType() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        ArgumentCaptor<AiDiagnosesRequest> captor = ArgumentCaptor.forClass(AiDiagnosesRequest.class);
        then(aiDiagnosesClient).should().requestDiagnoses(captor.capture());
        assertThat(captor.getValue()).isEqualTo(new AiDiagnosesRequest(DIAGNOSES_ID.toString(), List.of(
                new AiDiagnosesRequest.Product(TEXT_IMAGE_PRODUCT_ID.toString(), List.of("상세 설명"),
                        List.of(S3_URL_PREFIX + "product-main/1.jpg", S3_URL_PREFIX + "product-detail/1.jpg"), null),
                new AiDiagnosesRequest.Product(URL_PRODUCT_ID.toString(), List.of(), List.of(), SOURCE_URL))));
    }

    @Test
    @DisplayName("텍스트·이미지 없이 상세페이지 URL만 있는 상품은 URL을 이미지 자리에 넣지 않고 sourceUrl로만 보낸다.")
    void requestDiagnoses_withUrlOnlyProduct_thenSendSourceUrlWithoutImages() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());
        AiDiagnosesRequestedEvent event = new AiDiagnosesRequestedEvent(DIAGNOSES_ID, List.of(
                new AiDiagnosesRequestedEvent.ProductInput(URL_PRODUCT_ID, SourceType.URL, SOURCE_URL, " ", List.of())));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event);

        // then
        ArgumentCaptor<AiDiagnosesRequest> captor = ArgumentCaptor.forClass(AiDiagnosesRequest.class);
        then(aiDiagnosesClient).should().requestDiagnoses(captor.capture());
        assertThat(captor.getValue().products()).containsExactly(
                new AiDiagnosesRequest.Product(URL_PRODUCT_ID.toString(), List.of(), List.of(), SOURCE_URL));
    }

    @Test
    @DisplayName("AI가 접수하면 응답의 상품별 실행 식별자를 저장한다.")
    void requestDiagnoses_whenAccepted_thenAssignRuns() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(diagnosesService).should().assignRuns(DIAGNOSES_ID,
                Map.of(TEXT_IMAGE_PRODUCT_ID, "run-1", URL_PRODUCT_ID, "run-2"));
    }

    @Test
    @DisplayName("AI가 요청을 받지 않았으면(429, 5xx, 연결 실패) 보낸 상품들을 대기로 되돌려 재요청을 기다린다.")
    void requestDiagnoses_whenNotReceived_thenReturnToPending() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willThrow(failure(Failure.NOT_RECEIVED, 503));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(diagnosesService).should().returnToPending(DIAGNOSES_ID, List.of(TEXT_IMAGE_PRODUCT_ID, URL_PRODUCT_ID));
        then(diagnosesService).should(never()).failRejectedRequest(any(), any());
    }

    @Test
    @DisplayName("AI가 접수했는지 모르면(읽기 타임아웃) 다시 보내지 않고 상품 상태도 바꾸지 않는다.")
    void requestDiagnoses_whenUnknown_thenKeepInProgress() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willThrow(failure(Failure.UNKNOWN, null));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(aiDiagnosesClient).should(times(1)).requestDiagnoses(any());
        then(diagnosesService).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("AI가 다시 보내도 실패할 요청으로 거절하면 보낸 상품들을 실패 처리한다.")
    void requestDiagnoses_whenRejected_thenFailProducts() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willThrow(failure(Failure.REJECTED, 422));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(diagnosesService).should().failRejectedRequest(DIAGNOSES_ID, List.of(TEXT_IMAGE_PRODUCT_ID, URL_PRODUCT_ID));
        then(diagnosesService).should(never()).returnToPending(any(), any());
    }

    @Test
    @DisplayName("이미 진행 중인 상품 때문에 거절(409)되면 그 상품을 빼고 나머지만 다시 요청해 실행 식별자를 저장한다.")
    void requestDiagnoses_whenConflict_thenRequestRemainingOnly() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any()))
                .willThrow(AiDiagnosesRequestException.conflict(List.of(TEXT_IMAGE_PRODUCT_ID.toString()), null))
                .willReturn(new AiDiagnosesAccepted(DIAGNOSES_ID.toString(), List.of(
                        new AiDiagnosesAccepted.AcceptedProduct(URL_PRODUCT_ID.toString(), "run-2", "accepted"))));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        ArgumentCaptor<AiDiagnosesRequest> captor = ArgumentCaptor.forClass(AiDiagnosesRequest.class);
        then(aiDiagnosesClient).should(times(2)).requestDiagnoses(captor.capture());
        assertThat(captor.getAllValues().get(1).products())
                .extracting(AiDiagnosesRequest.Product::productId)
                .containsExactly(URL_PRODUCT_ID.toString());
        then(diagnosesService).should().assignRuns(DIAGNOSES_ID, Map.of(URL_PRODUCT_ID, "run-2"));
        then(diagnosesService).should().failConflictedRequest(DIAGNOSES_ID, List.of(TEXT_IMAGE_PRODUCT_ID));
    }

    @Test
    @DisplayName("모든 상품이 이전 진단 진행 중이라 거절(409)되면 다시 요청하지 않고 모두 실패 처리한다.")
    void requestDiagnoses_whenAllConflict_thenFailAllAndStop() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willThrow(AiDiagnosesRequestException.conflict(
                List.of(TEXT_IMAGE_PRODUCT_ID.toString(), URL_PRODUCT_ID.toString()), null));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(aiDiagnosesClient).should(times(1)).requestDiagnoses(any());
        then(diagnosesService).should().failConflictedRequest(DIAGNOSES_ID, List.of(TEXT_IMAGE_PRODUCT_ID, URL_PRODUCT_ID));
        then(diagnosesService).should(never()).assignRuns(any(), any());
        then(diagnosesService).should(never()).returnToPending(any(), any());
    }

    @Test
    @DisplayName("409 응답에서 보낸 상품 중 충돌 상품을 찾지 못하면 같은 요청을 반복하지 않고 멈춘다.")
    void requestDiagnoses_whenConflictWithoutKnownProduct_thenStop() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willThrow(AiDiagnosesRequestException.conflict(List.of(), null));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(aiDiagnosesClient).should(times(1)).requestDiagnoses(any());
        then(diagnosesService).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("409로 충돌 상품을 빼고 다시 요청했는데 AI가 받지 않으면 다시 보낸 상품만 대기로 되돌린다.")
    void requestDiagnoses_whenConflictThenNotReceived_thenReturnRemainingToPending() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any()))
                .willThrow(AiDiagnosesRequestException.conflict(List.of(TEXT_IMAGE_PRODUCT_ID.toString()), null))
                .willThrow(failure(Failure.NOT_RECEIVED, 503));

        // when
        aiDiagnosesRequestUseCase.requestDiagnoses(event());

        // then
        then(diagnosesService).should().returnToPending(DIAGNOSES_ID, List.of(URL_PRODUCT_ID));
    }

    @Test
    @DisplayName("요청 결과를 저장하다 실패해도 예외를 밖으로 던지지 않는다.")
    void requestDiagnoses_whenSaveFails_thenSwallow() {
        // given: 비동기 리스너와 스케줄러에서 호출하므로 예외를 던져도 받을 곳이 없다.
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());
        willThrow(new IllegalStateException("db down")).given(diagnosesService).assignRuns(any(), any());

        // when & then
        assertThatCode(() -> aiDiagnosesRequestUseCase.requestDiagnoses(event())).doesNotThrowAnyException();
    }

    private AiDiagnosesRequestedEvent event() {
        return new AiDiagnosesRequestedEvent(DIAGNOSES_ID, List.of(
                new AiDiagnosesRequestedEvent.ProductInput(TEXT_IMAGE_PRODUCT_ID, SourceType.TEXT_IMAGE, null,
                        "상세 설명", List.of("product-main/1.jpg", "product-detail/1.jpg")),
                new AiDiagnosesRequestedEvent.ProductInput(URL_PRODUCT_ID, SourceType.URL, SOURCE_URL,
                        null, List.of())));
    }

    private AiDiagnosesAccepted accepted() {
        return new AiDiagnosesAccepted(DIAGNOSES_ID.toString(), List.of(
                new AiDiagnosesAccepted.AcceptedProduct(TEXT_IMAGE_PRODUCT_ID.toString(), "run-1", "accepted"),
                new AiDiagnosesAccepted.AcceptedProduct(URL_PRODUCT_ID.toString(), "run-2", "accepted")));
    }

    private AiDiagnosesRequestException failure(Failure failure, Integer status) {
        return AiDiagnosesRequestException.of(failure, status, null);
    }
}
