package kakaotech.kangwon3.beforeselling.global.infra.ai;

import kakaotech.kangwon3.beforeselling.global.config.properties.AiServerProperties;
import kakaotech.kangwon3.beforeselling.global.config.properties.InternalApiProperties;
import kakaotech.kangwon3.beforeselling.global.infra.ai.AiDiagnosesRequestException.Failure;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesConflict;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiDiagnosesRequest;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeAccepted;
import kakaotech.kangwon3.beforeselling.global.infra.ai.dto.AiResumeRequest;
import kakaotech.kangwon3.beforeselling.global.security.filter.InternalTokenFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.net.ConnectException;
import java.net.NoRouteToHostException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.util.List;

/**
 * AI 서버에 진단 접수. 결과는 상품별 콜백(/internal/v1/ai/products/{productId})으로 따로 전달.
 * 요청에는 콜백과 같은 내부 토큰(X-Internal-Token)을 함께 전달.
 */
@Component
@RequiredArgsConstructor
public class AiDiagnosesClient {

    private static final String DIAGNOSE_PATH = "/diagnose/content";
    private static final String RESUME_PATH = "/diagnose/resume";
    private static final String CONNECT_TIMEOUT_MESSAGE = "Connect timed out";

    private final RestClient restClient;
    private final AiServerProperties aiServerProperties;
    private final InternalApiProperties internalApiProperties;

    /**
     * @throws AiDiagnosesRequestException 접수(202)되지 않았거나 접수 여부를 모를 때
     */
    public AiDiagnosesAccepted requestDiagnoses(AiDiagnosesRequest request) {
        try {
            AiApiResponse<AiDiagnosesAccepted> response = restClient.post()
                    .uri(aiServerProperties.baseUrl() + aiServerProperties.diagnosePathPrefix() + DIAGNOSE_PATH)
                    .header(InternalTokenFilter.HEADER_NAME, internalApiProperties.token())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request)
                    .retrieve()
                    .body(new ParameterizedTypeReference<>() {
                    });

            // 접수는 됐지만 실행 식별자를 알 수 없어 접수 여부를 모를 때와 같이 처리한다.
            if (response == null || response.data() == null || response.data().products() == null) {
                throw AiDiagnosesRequestException.of(Failure.UNKNOWN, HttpStatus.ACCEPTED.value(), null);
            }
            return response.data();
        } catch (RestClientException e) {
            throw classify(e);
        }
    }

    // AI가 요청을 받았는지로 예외 분류. 판단이 어려우면 다시 보내지 않도록 UNKNOWN으로 처리.
    static AiDiagnosesRequestException classify(RestClientException e) {
        if (e instanceof RestClientResponseException response) {
            return classifyStatus(response);
        }
        if (e instanceof ResourceAccessException && isNotConnected(e.getCause())) {
            return AiDiagnosesRequestException.of(Failure.NOT_RECEIVED, null, e);
        }
        // 읽기 타임아웃, 202 본문 변환 실패 등
        return AiDiagnosesRequestException.of(Failure.UNKNOWN, null, e);
    }

    private static AiDiagnosesRequestException classifyStatus(RestClientResponseException e) {
        HttpStatusCode status = e.getStatusCode();
        if (status.isSameCodeAs(HttpStatus.CONFLICT)) {
            return AiDiagnosesRequestException.conflict(readConflictProductIds(e), e);
        }
        if (status.isSameCodeAs(HttpStatus.TOO_MANY_REQUESTS)
                || (status.is5xxServerError() && !status.isSameCodeAs(HttpStatus.NOT_IMPLEMENTED))) {
            return AiDiagnosesRequestException.of(Failure.NOT_RECEIVED, status.value(), e);
        }
        return AiDiagnosesRequestException.of(Failure.REJECTED, status.value(), e);
    }

    private static List<String> readConflictProductIds(RestClientResponseException e) {
        try {
            AiApiResponse<AiDiagnosesConflict> body = e.getResponseBodyAs(new ParameterizedTypeReference<>() {
            });
            if (body == null || body.data() == null || body.data().conflictProductIds() == null) {
                return List.of();
            }
            return body.data().conflictProductIds();
        } catch (RuntimeException ignored) {
            return List.of();
        }
    }

    private static boolean isNotConnected(Throwable cause) {
        return cause instanceof ConnectException
                || cause instanceof NoRouteToHostException
                || cause instanceof UnknownHostException
                || (cause instanceof SocketTimeoutException
                && CONNECT_TIMEOUT_MESSAGE.equalsIgnoreCase(cause.getMessage()));
    }

    /**
     * 답변 대기 상품의 재진단 접수
     */
    public AiResumeAccepted requestResume(AiResumeRequest request) {
        AiApiResponse<AiResumeAccepted> response = restClient.post()
                .uri(aiServerProperties.baseUrl() + aiServerProperties.diagnosePathPrefix() + RESUME_PATH)
                .header(InternalTokenFilter.HEADER_NAME, internalApiProperties.token())
                .contentType(MediaType.APPLICATION_JSON)
                .body(request)
                .retrieve()
                .body(new ParameterizedTypeReference<>() {
                });

        return response == null ? null : response.data();
    }
}
