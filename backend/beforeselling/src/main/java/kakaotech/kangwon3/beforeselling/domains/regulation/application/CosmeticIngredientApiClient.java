package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import java.net.URI;
import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.CosmeticIngredient;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.CosmeticIngredientRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * 식약처 화장품 규제 원료 API를 호출하여 규제 정보를 수집·저장하는 클라이언트.
 * data.go.kr 서비스키가 필요하며, JSON 응답을 파싱한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class CosmeticIngredientApiClient {

    private static final String BASE_URL =
            "https://apis.data.go.kr/1471000/CsmtcsReglMaterialInfoService/getCsmtcsReglMaterialInfoService";

    private final RestClient restClient;
    private final CosmeticIngredientRepository cosmeticIngredientRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${data-go-kr.service-key}")
    private String serviceKey;

    /**
     * 화장품 규제 원료 정보를 페이지 단위로 조회하여 DB에 저장한다.
     * @param pageNo 페이지 번호
     * @param numOfRows 한 페이지당 건수
     * @return 저장 성공 여부
     */
    public boolean fetchAndSave(int pageNo, int numOfRows) {
        // serviceKey는 URL 인코딩된 상태로 저장되어 있으므로 직접 삽입
        String url = BASE_URL + "?serviceKey=" + serviceKey
                + "&pageNo=" + pageNo
                + "&numOfRows=" + numOfRows
                + "&type=json";

        // .uri(String)은 내부에서 재인코딩하여 serviceKey가 깨지므로 URI 객체로 전달
        String json = restClient.get()
                .uri(URI.create(url))
                .retrieve()
                .body(String.class);

        try {
            JsonNode root = objectMapper.readTree(json);
            JsonNode items = root.path("body").path("items");

            // 조회 결과가 없을 때
            if (items.isMissingNode() || items.isEmpty()) {
                return false;
            }

            List<CosmeticIngredient> result = new ArrayList<>();

            // 결과가 2건 이상이면 배열, 1건이면 단일 객체
            if (items.isArray()) {
                for (JsonNode node : items) {
                    result.add(parseIngredient(node));
                }
            } else {
                result.add(parseIngredient(items));
            }

            cosmeticIngredientRepository.saveAll(result);
            log.info("화장품 규제원료 {}건 저장 완료 (page={})", result.size(), pageNo);
            return true;
        } catch (Exception e) {
            log.error("화장품 규제원료 파싱 실패 (page={}): {}", pageNo, e.getMessage());
            return false;
        }
    }

    /**
     * JSON 노드 하나를 CosmeticIngredient 엔티티로 변환한다.
     * @param node 화장품 규제원료 JSON 노드
     * @return CosmeticIngredient 엔티티
     */
    private CosmeticIngredient parseIngredient(JsonNode node) {
        return CosmeticIngredient.fromApi(
                node.path("INGR_STD_NAME").asText(""),   // 원료 표준명 (한글)
                node.path("INGR_ENG_NAME").asText(""),   // 원료 영문명
                node.path("PROH_NATIONAL").asText(""),   // 사용금지 국가
                node.path("LIMIT_NATIONAL").asText("")   // 사용제한 국가
        );
    }
}
