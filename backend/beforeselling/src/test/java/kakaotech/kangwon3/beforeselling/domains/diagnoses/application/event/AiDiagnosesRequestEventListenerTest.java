package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.event;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesClient;
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
import org.springframework.web.client.ResourceAccessException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class AiDiagnosesRequestEventListenerTest {

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
    private AiDiagnosesRequestEventListener listener;

    @BeforeEach
    void setUp() {
        lenient().when(s3UrlKeyCodec.toUrl(anyString())).thenAnswer(invocation -> S3_URL_PREFIX + invocation.getArgument(0));
    }

    @Test
    @DisplayName("텍스트·이미지 상품은 텍스트와 이미지 URL로, URL만 있는 상품은 상세페이지 URL로 AI에 진단을 요청한다.")
    void handle_thenRequestDiagnosesBySourceType() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());

        // when
        listener.handle(event());

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
    void handle_withUrlOnlyProduct_thenSendSourceUrlWithoutImages() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());
        AiDiagnosesRequestedEvent event = new AiDiagnosesRequestedEvent(DIAGNOSES_ID, List.of(
                new AiDiagnosesRequestedEvent.ProductInput(URL_PRODUCT_ID, SourceType.URL, SOURCE_URL, " ", List.of())));

        // when
        listener.handle(event);

        // then
        ArgumentCaptor<AiDiagnosesRequest> captor = ArgumentCaptor.forClass(AiDiagnosesRequest.class);
        then(aiDiagnosesClient).should().requestDiagnoses(captor.capture());
        assertThat(captor.getValue().products()).containsExactly(
                new AiDiagnosesRequest.Product(URL_PRODUCT_ID.toString(), List.of(), List.of(), SOURCE_URL));
    }

    @Test
    @DisplayName("AI가 접수하면 응답의 상품별 실행 식별자를 저장한다.")
    void handle_whenAccepted_thenAssignRuns() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(accepted());

        // when
        listener.handle(event());

        // then
        then(diagnosesService).should().assignRuns(DIAGNOSES_ID,
                Map.of(TEXT_IMAGE_PRODUCT_ID, "run-1", URL_PRODUCT_ID, "run-2"));
    }

    @Test
    @DisplayName("AI 요청이 실패하면 예외를 밖으로 던지지 않고 실행 식별자도 저장하지 않는다.")
    void handle_whenRequestFails_thenSwallowAndSkipAssign() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willThrow(new ResourceAccessException("connection refused"));

        // when & then
        assertThatCode(() -> listener.handle(event())).doesNotThrowAnyException();
        then(diagnosesService).should(never()).assignRuns(any(), any());
    }

    @Test
    @DisplayName("AI 응답에 접수 내용이 없으면 실행 식별자를 저장하지 않는다.")
    void handle_whenAcceptedBodyMissing_thenSkipAssign() {
        // given
        given(aiDiagnosesClient.requestDiagnoses(any())).willReturn(null);

        // when & then
        assertThatCode(() -> listener.handle(event())).doesNotThrowAnyException();
        then(diagnosesService).should(never()).assignRuns(any(), any());
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
}
