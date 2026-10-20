package kakaotech.kangwon3.beforeselling.global.infra.ai;

import kakaotech.kangwon3.beforeselling.global.config.properties.AiServerProperties;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

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
                        List.of("https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1.jpg")),
                new AiDiagnosesRequest.Product("product-2", List.of(),
                        List.of("https://bucket.s3.ap-northeast-2.amazonaws.com/product-detail/2.jpg"))));

        server.expect(requestTo(DIAGNOSE_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json("""
                        {
                          "diagnosisId": "diagnosis-1",
                          "products": [
                            {"productId": "product-1", "textBlocks": ["상세 설명"],
                             "imagesBase64": ["https://bucket.s3.ap-northeast-2.amazonaws.com/product-main/1.jpg"]},
                            {"productId": "product-2", "textBlocks": [],
                             "imagesBase64": ["https://bucket.s3.ap-northeast-2.amazonaws.com/product-detail/2.jpg"]}
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
}
