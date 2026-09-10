package kakaotech.kangwon3.beforeselling.global.util;

import java.net.URI;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class DataGoKrApiCaller {

    private final RestClient restClient;

    @Value("${data-go-kr.service-key}")
    private String serviceKey;

    /**
     * data.go.kr API를 호출하여 응답 문자열을 반환한다.
     * serviceKey 이중인코딩 방지를 위해 URI 객체로 변환하여 요청한다.
     */
    public String call(String baseUrl, String params) {
        String url = baseUrl + "?serviceKey=" + serviceKey + "&" + params;
        return restClient.get()
                .uri(URI.create(url))
                .retrieve()
                .body(String.class);
    }
}
