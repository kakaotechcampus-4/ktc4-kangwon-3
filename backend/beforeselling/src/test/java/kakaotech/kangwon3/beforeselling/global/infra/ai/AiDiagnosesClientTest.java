package kakaotech.kangwon3.beforeselling.global.infra.ai;

import kakaotech.kangwon3.beforeselling.global.config.properties.AiServerProperties;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

class AiDiagnosesClientTest {

    private static final String BASE_URL = "http://ai-server:8000";
    private static final String DIAGNOSE_URL = BASE_URL + "/api/ai/v1/diagnose/content";
    private static final String RESUME_URL = BASE_URL + "/api/ai/v1/diagnose/resume";

    private MockRestServiceServer server;
    private AiDiagnosesClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        client = new AiDiagnosesClient(builder.build(), new AiServerProperties(BASE_URL));
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
    @DisplayName("AI가 오류로 응답하면 예외가 발생한다.")
    void requestDiagnoses_whenServerError_thenThrow() {
        // given
        server.expect(requestTo(DIAGNOSE_URL)).andRespond(withServerError());

        // when & then
        assertThatThrownBy(() -> client.requestDiagnoses(new AiDiagnosesRequest("diagnosis-1", List.of())))
                .isInstanceOf(RestClientException.class);
    }

    @Test
    @DisplayName("AI가 요청을 거절(409)하면 예외가 발생한다.")
    void requestDiagnoses_whenConflict_thenThrow() {
        // given
        server.expect(requestTo(DIAGNOSE_URL)).andRespond(withStatus(HttpStatus.CONFLICT));

        // when & then
        assertThatThrownBy(() -> client.requestDiagnoses(new AiDiagnosesRequest("diagnosis-1", List.of())))
                .isInstanceOf(RestClientException.class);
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
