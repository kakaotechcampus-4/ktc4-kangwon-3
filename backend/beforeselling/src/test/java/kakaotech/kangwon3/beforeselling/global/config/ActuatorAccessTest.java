package kakaotech.kangwon3.beforeselling.global.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalManagementPort;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.web.client.RestClient;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "management.server.port=0",
                // 테스트 환경엔 Redis가 없어 health가 DOWN(503)이 되므로 Redis 지표만 끈다.
                "management.health.redis.enabled=false"
        })
@ActiveProfiles("test")
class ActuatorAccessTest {

    @LocalServerPort
    private int serverPort;

    @LocalManagementPort
    private int managementPort;

    private final RestClient restClient = RestClient.builder()
            .defaultStatusHandler(status -> true, (request, response) -> { })
            .build();

    @Test
    @DisplayName("관리 포트의 prometheus 엔드포인트는 인증 없이 조회되고 HTTP 요청 메트릭을 포함한다.")
    void prometheus_onManagementPort_withoutAuthentication_thenOk() {
        // given: 서비스 포트로 요청을 한 번 보내 http.server.requests 메트릭을 만든다.
        get(serverPort, "/v3/api-docs");

        // when & then: 응답이 클라이언트에 먼저 flush된 뒤 메트릭이 기록되므로, 나타날 때까지 기다린다.
        await().atMost(Duration.ofSeconds(5)).untilAsserted(() -> {
            ResponseEntity<String> response = get(managementPort, "/actuator/prometheus");

            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
            assertThat(response.getBody())
                    .contains("http_server_requests_seconds_bucket")
                    .contains("application=\"beforeselling\"");
        });
    }

    @Test
    @DisplayName("관리 포트의 health 엔드포인트는 인증 없이 UP을 반환한다.")
    void health_onManagementPort_withoutAuthentication_thenUp() {
        // when
        ResponseEntity<String> response = get(managementPort, "/actuator/health");

        // then
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("\"status\":\"UP\"");
    }

    @Test
    @DisplayName("서비스 포트에서는 actuator 엔드포인트가 노출되지 않는다.")
    void actuator_onServerPort_thenNotExposed() {
        // when
        ResponseEntity<String> response = get(serverPort, "/actuator/prometheus");

        // then
        assertThat(response.getStatusCode().is2xxSuccessful()).isFalse();
    }

    private ResponseEntity<String> get(int port, String path) {
        return restClient.get()
                .uri("http://localhost:" + port + path)
                .retrieve()
                .toEntity(String.class);
    }
}
