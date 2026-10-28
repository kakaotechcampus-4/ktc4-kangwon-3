package kakaotech.kangwon3.beforeselling.global.infra.ai;

import kakaotech.kangwon3.beforeselling.global.config.properties.AiServerProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.InternalApiProperties;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class AiDiagnosesClientTest {

    private static final String BASE_URL = "http://ai-server:8000";
    private static final String DIAGNOSE_URL = BASE_URL + "/api/ai/v1/diagnose/content";
    private static final String RESUME_URL = BASE_URL + "/api/ai/v1/diagnose/resume";
    private static final String INTERNAL_TOKEN = "test-internal-token-at-least-32-characters";

    private MockRestServiceServer server;
    private AiDiagnosesClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new AiDiagnosesClient(builder.build(), new AiServerProperties(BASE_URL),
                new InternalApiProperties(INTERNAL_TOKEN));
    }

    @Test
    @DisplayName("진단서의 상품들을 camelCase 본문으로 AI 진단 접수 API에 보내고, 202 응답의 상품별 runId를 돌려준다.")
    void requestDiagnoses_thenPostCamelCaseBodyAndReturnRunIds() {
        // given
        AiDiagnosesRequest request = new AiDiagnosesRequest("diagnosis-1", List.of(
                new AiDiagnosesRequest.Product("product-1", List.of("상세 설명"),
                        List.of("https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1.jpg"), null),
                new AiDiagnosesRequest.Product("product-2", List.of(), List.of(),
                        "https://ko.aliexpress.com/item/100500628491")));

        server.expect(requestTo(DIAGNOSE_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json("""
                        {
                          "diagnosisId": "diagnosis-1",
                          "products": [
                            {"productId": "product-1", "textBlocks": ["상세 설명"],
                             "imageUrls": ["https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1.jpg"],
                             "sourceUrl": null},
                            {"productId": "product-2", "textBlocks": [], "imageUrls": [],
                             "sourceUrl": "https://ko.aliexpress.com/item/100500628491"}
                          ]
                        }
                        """, true))
                .andRespond(withStatus(HttpStatus.ACCEPTED)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("""
                                {
                                  "code": "OK",
                                  "message": "접수되었습니다.",
                                  "details": null,
                                  "data": {
                                    "diagnosisId": "diagnosis-1",
                                    "products": [
                                      {"productId": "product-1", "runId": "run-1", "status": "accepted"},
                                      {"productId": "product-2", "runId": "run-2", "status": "accepted"}
                                    ]
                                  }
                                }
                                """));

        // when
        AiDiagnosesAccepted accepted = client.requestDiagnoses(request);

        // then
        server.verify();
        assertThat(accepted.diagnosisId()).isEqualTo("diagnosis-1");
        assertThat(accepted.products())
                .extracting(AiDiagnosesAccepted.AcceptedProduct::productId, AiDiagnosesAccepted.AcceptedProduct::runId)
                .containsExactly(
                        tuple("product-1", "run-1"),
                        tuple("product-2", "run-2"));
    }

    @Test
    @DisplayName("AI 진단 접수 요청에 내부 토큰 헤더를 담아 보낸다.")
    void requestDiagnoses_thenSendInternalTokenHeader() {
        // given
        server.expect(requestTo(DIAGNOSE_URL))
                .andExpect(header("X-Internal-Token", INTERNAL_TOKEN))
                .andRespond(withStatus(HttpStatus.ACCEPTED)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("""
                                {"code": "OK", "message": "접수되었습니다.", "details": null,
                                 "data": {"diagnosisId": "diagnosis-1", "products": []}}
                                """));

        // when
        client.requestDiagnoses(emptyRequest());

        // then
        server.verify();
    }

    @Test
    @DisplayName("AI가 진행 중인 상품 때문에 거절(409)하면 충돌 상품 ID를 담은 충돌 예외가 발생한다.")
    void requestDiagnoses_whenConflict_thenThrowConflictWithProductIds() {
        // given
        server.expect(requestTo(DIAGNOSE_URL))
                .andRespond(withStatus(HttpStatus.CONFLICT)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("""
                                {
                                  "code": "AI_SESSION_CONFLICT",
                                  "message": "이미 진행 중인 상품이 있습니다.",
                                  "details": null,
                                  "data": {"conflictProductIds": ["product-1"]}
                                }
                                """));

        // when & then
        assertThatThrownBy(() -> client.requestDiagnoses(emptyRequest()))
                .isInstanceOfSatisfying(AiDiagnosesRequestException.class, e -> {
                    assertThat(e.getFailure()).isEqualTo(AiDiagnosesRequestException.Failure.CONFLICT);
                    assertThat(e.getConflictProductIds()).containsExactly("product-1");
                });
    }

    @Test
    @DisplayName("409 응답 본문에서 충돌 상품을 읽지 못하면 충돌 상품이 빈 충돌 예외가 발생한다.")
    void requestDiagnoses_whenConflictBodyUnreadable_thenThrowConflictWithoutProductIds() {
        // given
        server.expect(requestTo(DIAGNOSE_URL)).andRespond(withStatus(HttpStatus.CONFLICT));

        // when & then
        assertThatThrownBy(() -> client.requestDiagnoses(emptyRequest()))
                .isInstanceOfSatisfying(AiDiagnosesRequestException.class, e -> {
                    assertThat(e.getFailure()).isEqualTo(AiDiagnosesRequestException.Failure.CONFLICT);
                    assertThat(e.getConflictProductIds()).isEmpty();
                });
    }

    @ParameterizedTest
    @ValueSource(ints = {429, 500, 502, 503, 504})
    @DisplayName("AI가 대기열 초과(429)나 서버 오류(5xx)로 응답하면 요청을 받지 않은 것으로 본다.")
    void requestDiagnoses_whenQueueFullOrServerError_thenThrowNotReceived(int status) {
        // given
        server.expect(requestTo(DIAGNOSE_URL)).andRespond(withStatus(HttpStatusCode.valueOf(status)));

        // when & then
        assertFailure(AiDiagnosesRequestException.Failure.NOT_RECEIVED);
    }

    @ParameterizedTest
    @ValueSource(ints = {400, 404, 405, 422, 501})
    @DisplayName("AI가 다시 보내도 실패할 오류(400·404·405·422·501)로 응답하면 거절된 것으로 본다.")
    void requestDiagnoses_whenPermanentError_thenThrowRejected(int status) {
        // given
        server.expect(requestTo(DIAGNOSE_URL)).andRespond(withStatus(HttpStatusCode.valueOf(status)));

        // when & then
        assertFailure(AiDiagnosesRequestException.Failure.REJECTED);
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "{\"code\": \"OK\", \"message\": \"접수되었습니다.\", \"data\": null}",
            "{\"code\": \"OK\", \"message\": \"접수되었습니다.\", \"data\": {\"diagnosisId\": \"diagnosis-1\", \"products\": null}}"
    })
    @DisplayName("AI가 접수(202)했지만 응답에 접수된 상품 정보가 없으면 접수 여부를 모르는 것으로 본다.")
    void requestDiagnoses_whenAcceptedWithoutProducts_thenThrowUnknown(String body) {
        // given
        server.expect(requestTo(DIAGNOSE_URL))
                .andRespond(withStatus(HttpStatus.ACCEPTED).contentType(MediaType.APPLICATION_JSON).body(body));

        // when & then
        assertFailure(AiDiagnosesRequestException.Failure.UNKNOWN);
    }

    @Test
    @DisplayName("AI가 접수(202)했지만 응답 본문을 읽지 못하면 접수 여부를 모르는 것으로 본다.")
    void requestDiagnoses_whenAcceptedBodyUnreadable_thenThrowUnknown() {
        // given
        server.expect(requestTo(DIAGNOSE_URL))
                .andRespond(withStatus(HttpStatus.ACCEPTED).contentType(MediaType.APPLICATION_JSON).body("{"));

        // when & then
        assertFailure(AiDiagnosesRequestException.Failure.UNKNOWN);
    }

    @Test
    @DisplayName("AI 서버에 연결하지 못하면(연결 거부) 요청을 받지 않은 것으로 본다.")
    void requestDiagnoses_whenConnectionRefused_thenThrowNotReceived() throws IOException {
        // given
        int closedPort;
        try (ServerSocket socket = new ServerSocket(0)) {
            closedPort = socket.getLocalPort();
        }
        AiDiagnosesClient realClient = realClient("http://localhost:" + closedPort, Duration.ofSeconds(1));

        // when & then
        assertThatThrownBy(() -> realClient.requestDiagnoses(emptyRequest()))
                .isInstanceOfSatisfying(AiDiagnosesRequestException.class, e ->
                        assertThat(e.getFailure()).isEqualTo(AiDiagnosesRequestException.Failure.NOT_RECEIVED));
    }

    @Test
    @DisplayName("요청을 보낸 뒤 응답을 기다리다 시간이 초과되면(읽기 타임아웃) 접수 여부를 모르는 것으로 본다.")
    void requestDiagnoses_whenReadTimeout_thenThrowUnknown() throws IOException {
        // given: 연결은 받지만 응답하지 않는 서버
        try (ServerSocket silentServer = new ServerSocket(0)) {
            AiDiagnosesClient realClient = realClient("http://localhost:" + silentServer.getLocalPort(),
                    Duration.ofMillis(200));

            // when & then
            assertThatThrownBy(() -> realClient.requestDiagnoses(emptyRequest()))
                    .isInstanceOfSatisfying(AiDiagnosesRequestException.class, e ->
                            assertThat(e.getFailure()).isEqualTo(AiDiagnosesRequestException.Failure.UNKNOWN));
        }
    }

    @Test
    @DisplayName("연결 시간이 초과되면 요청을 받지 않은 것으로 본다.")
    void classify_whenConnectTimeout_thenNotReceived() {
        // given: HttpURLConnection은 연결·읽기 타임아웃을 같은 예외로 던지고 메시지만 다르다.
        ResourceAccessException exception = new ResourceAccessException("I/O error",
                new SocketTimeoutException("Connect timed out"));

        // when
        AiDiagnosesRequestException classified = AiDiagnosesClient.classify(exception);

        // then
        assertThat(classified.getFailure()).isEqualTo(AiDiagnosesRequestException.Failure.NOT_RECEIVED);
    }

    @Test
    @DisplayName("AI 서버 주소를 찾지 못하면 요청을 받지 않은 것으로 본다.")
    void classify_whenUnknownHost_thenNotReceived() {
        // given
        ResourceAccessException exception = new ResourceAccessException("I/O error",
                new UnknownHostException("ai-server"));

        // when
        AiDiagnosesRequestException classified = AiDiagnosesClient.classify(exception);

        // then
        assertThat(classified.getFailure()).isEqualTo(AiDiagnosesRequestException.Failure.NOT_RECEIVED);
    }

    private void assertFailure(AiDiagnosesRequestException.Failure failure) {
        assertThatThrownBy(() -> client.requestDiagnoses(emptyRequest()))
                .isInstanceOfSatisfying(AiDiagnosesRequestException.class, e ->
                        assertThat(e.getFailure()).isEqualTo(failure));
    }

    private AiDiagnosesRequest emptyRequest() {
        return new AiDiagnosesRequest("diagnosis-1", List.of());
    }

    // 실제 HTTP 연결로 연결 실패·읽기 타임아웃을 확인한다. 운영과 같은 요청 팩토리를 쓴다.
    private AiDiagnosesClient realClient(String baseUrl, Duration readTimeout) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(1));
        factory.setReadTimeout(readTimeout);
        return new AiDiagnosesClient(RestClient.builder().requestFactory(factory).build(),
                new AiServerProperties(baseUrl), new InternalApiProperties(INTERNAL_TOKEN));
    }

    @Test
    @DisplayName("답변을 camelCase 본문으로 AI 재진단 API에 보내고, 202 응답의 새 runId를 돌려준다.")
    void requestResume_thenPostCamelCaseBodyAndReturnNewRunId() {
        // given
        AiResumeRequest request = new AiResumeRequest("diagnosis-1", "product-1", "run-1", 1, List.of(
                new AiResumeRequest.Answer("battery_only", "네")));

        server.expect(requestTo(RESUME_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json("""
                        {
                          "diagnosisId": "diagnosis-1",
                          "productId": "product-1",
                          "runId": "run-1",
                          "questionRound": 1,
                          "answers": [{"questionKey": "battery_only", "answerText": "네"}]
                        }
                        """, true))
                .andRespond(withStatus(HttpStatus.ACCEPTED)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("""
                                {
                                  "code": "OK",
                                  "message": "재진단 요청이 접수되었습니다.",
                                  "details": null,
                                  "data": {"productId": "product-1", "runId": "run-2", "status": "accepted"}
                                }
                                """));

        // when
        AiResumeAccepted accepted = client.requestResume(request);

        // then
        server.verify();
        assertThat(accepted).isEqualTo(new AiResumeAccepted("product-1", "run-2", "accepted"));
    }

    @Test
    @DisplayName("AI 재진단 요청에 내부 토큰 헤더를 담아 보낸다.")
    void requestResume_thenSendInternalTokenHeader() {
        // given
        server.expect(requestTo(RESUME_URL))
                .andExpect(header("X-Internal-Token", INTERNAL_TOKEN))
                .andRespond(withStatus(HttpStatus.ACCEPTED)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("""
                                {"code": "OK", "message": "재진단 요청이 접수되었습니다.", "details": null,
                                 "data": {"productId": "product-1", "runId": "run-2", "status": "accepted"}}
                                """));

        // when
        client.requestResume(new AiResumeRequest("diagnosis-1", "product-1", "run-1", 1, List.of()));

        // then
        server.verify();
    }

    @Test
    @DisplayName("AI가 재진단을 거절하면 예외에서 응답 본문의 code를 읽을 수 있다.")
    void requestResume_whenRejected_thenExceptionCarriesCode() {
        // given
        server.expect(requestTo(RESUME_URL))
                .andRespond(withStatus(HttpStatus.NOT_FOUND)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body("""
                                {"code": "AI_SESSION_NOT_FOUND", "message": "진단 세션을 찾을 수 없습니다.", "details": null, "data": null}
                                """));

        // when & then
        assertThatThrownBy(() -> client.requestResume(
                new AiResumeRequest("diagnosis-1", "product-1", "run-1", 1, List.of())))
                .isInstanceOfSatisfying(RestClientResponseException.class, e ->
                        assertThat(e.getResponseBodyAs(AiApiResponse.class).code()).isEqualTo("AI_SESSION_NOT_FOUND"));
    }
}
