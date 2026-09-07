package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import org.springframework.http.HttpMethod;
import org.springframework.http.codec.HttpMessageWriter;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.mock.http.client.reactive.MockClientHttpRequest;
import org.springframework.web.reactive.function.BodyInserter;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ExchangeStrategies;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** WebClient 요청 폼바디를 테스트에서 문자열로 읽기 위한 테스트 전용 헬퍼. */
final class WebClientRequestBodyReader {

    private WebClientRequestBodyReader() {
    }

    static String readBodyAsString(ClientRequest request) {
        MockClientHttpRequest httpRequest = new MockClientHttpRequest(HttpMethod.POST, request.url());
        BodyInserter.Context context = new BodyInserter.Context() {
            @Override
            public List<HttpMessageWriter<?>> messageWriters() {
                return ExchangeStrategies.withDefaults().messageWriters();
            }

            @Override
            public Optional<ServerHttpRequest> serverRequest() {
                return Optional.empty();
            }

            @Override
            public Map<String, Object> hints() {
                return Collections.emptyMap();
            }
        };
        request.body().insert(httpRequest, context).block();
        return httpRequest.getBodyAsString().block();
    }
}
