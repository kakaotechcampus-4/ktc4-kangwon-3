package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.MedicalDevice;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.MedicalDeviceRepository;
import kakaotech.kangwon3.beforeselling.global.util.DataGoKrApiCaller;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * 식약처 의료기기 품목정보 API를 호출하여 품목 정보를 수집·저장하는 클라이언트.
 * data.go.kr 서비스키가 필요하며, JSON 응답을 파싱한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MedicalDeviceApiClient {

    private static final String BASE_URL =
            "https://apis.data.go.kr/1471000/MdeqPrdlstInfoService02/getMdeqPrdlstInfoInq02";

    private final DataGoKrApiCaller apiCaller;
    private final MedicalDeviceRepository medicalDeviceRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 의료기기 품목정보를 페이지 단위로 조회하여 DB에 저장한다.
     * @param pageNo 페이지 번호
     * @param numOfRows 한 페이지당 건수
     * @return 저장 성공 여부
     */
    public boolean fetchAndSave(int pageNo, int numOfRows) {
        String json = apiCaller.call(BASE_URL,
                "pageNo=" + pageNo + "&numOfRows=" + numOfRows + "&type=json");

        try {
            JsonNode root = objectMapper.readTree(json);
            JsonNode items = root.path("body").path("items");

            // 조회 결과가 없을 때
            if (items.isMissingNode() || items.isEmpty()) {
                return false;
            }

            List<MedicalDevice> result = new ArrayList<>();

            // 결과가 2건 이상이면 배열, 1건이면 단일 객체
            if (items.isArray()) {
                for (JsonNode node : items) {
                    // 각 원소가 "item" 객체로 감싸져 있음
                    result.add(parseDevice(node.path("item")));
                }
            } else {
                result.add(parseDevice(items.path("item")));
            }

            medicalDeviceRepository.saveAll(result);
            log.info("의료기기 품목 {}건 저장 완료 (page={})", result.size(), pageNo);
            return true;
        } catch (Exception e) {
            log.error("의료기기 품목 파싱 실패 (page={}): {}", pageNo, e.getMessage());
            return false;
        }
    }

    /**
     * JSON 노드 하나를 MedicalDevice 엔티티로 변환한다.
     * @param node 의료기기 품목 JSON 노드
     * @return MedicalDevice 엔티티
     */
    private MedicalDevice parseDevice(JsonNode node) {
        return MedicalDevice.fromApi(
                node.path("MDEQ_PRDLST_SN").asText(""),      // 의료기기 품목 일련번호
                node.path("PRDLST_NM").asText(""),            // 품목명
                node.path("MDEQ_CLSF_NO").asText(""),        // 품목분류번호
                node.path("CLSF_NO_GRAD_CD").asText(""),     // 등급
                node.path("PRMSN_DCLR_DIVS_NM").asText(""),  // 허가/신고 구분
                node.path("INDT_NM").asText(""),              // 업종명
                node.path("USE_PURPS_CONT").asText("")        // 사용목적
        );
    }
}
