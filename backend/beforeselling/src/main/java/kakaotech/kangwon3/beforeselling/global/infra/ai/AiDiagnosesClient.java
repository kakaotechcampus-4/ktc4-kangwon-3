package kakaotech.kangwon3.beforeselling.global.infra.ai;

import kakaotech.kangwon3.beforeselling.global.config.properties.AiServerProperties;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * AI 서버에 진단 접수. 결과는 상품별 콜백(/internal/v1/ai/products/{productId})으로 따로 전달.
 */
@Component
@RequiredArgsConstructor
public class AiDiagnosesClient {

    private static final String DIAGNOSE_PATH = "/api/ai/v1/diagnose/content";

    private final RestClient restClient;
    private final AiServerProperties aiServerProperties;

    public AiDiagnosesAccepted requestDiagnoses(AiDiagnosesRequest request) {
        AiApiResponse<AiDiagnosesAccepted> response = restClient.post()
                .uri(aiServerProperties.baseUrl() + DIAGNOSE_PATH)
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        return response == null ? null : response.data();
    }
}
