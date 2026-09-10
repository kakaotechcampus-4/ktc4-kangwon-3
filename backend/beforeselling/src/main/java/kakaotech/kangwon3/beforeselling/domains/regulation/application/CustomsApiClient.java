package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.CustomsConfirmation;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.CustomsConfirmationRepository;
import kakaotech.kangwon3.beforeselling.global.util.DataGoKrApiCaller;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * 관세청 세관장확인대상물품 API를 호출하여 확인대상 정보를 수집·저장하는 클라이언트.
 * data.go.kr 서비스키가 필요하며, XML 응답을 파싱한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class CustomsApiClient {

    private static final String BASE_URL =
            "https://apis.data.go.kr/1220000/retrieveCcctLworCd/getRetrieveCcctLworCd";
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final DataGoKrApiCaller apiCaller;
    private final CustomsConfirmationRepository customsConfirmationRepository;
    private final XmlMapper xmlMapper = new XmlMapper();

    /**
     * 품목코드로 세관장확인대상물품을 조회하여 DB에 저장한다.
     * @param hsCode 품목코드 (HS코드)
     * @param importExport 수출입구분 (1:수출, 2:수입)
     * @return 저장 성공 여부
     */
    public boolean fetchAndSave(String hsCode, String importExport) {
        String xml = apiCaller.call(BASE_URL, "hsSgn=" + hsCode + "&imexTpcd=" + importExport);

        try {
            JsonNode root = xmlMapper.readTree(xml);
            JsonNode items = root.path("body").path("items").path("item");

            // 조회 결과가 없을 때
            if (items.isMissingNode() || items.isEmpty()) {
                return false;
            }

            List<CustomsConfirmation> result = new ArrayList<>();

            // 결과가 2건 이상이면 배열, 1건이면 단일 객체 (XML 특성)
            if (items.isArray()) {
                for (JsonNode node : items) {
                    result.add(parseConfirmation(node));
                }
            } else {
                result.add(parseConfirmation(items));
            }

            customsConfirmationRepository.saveAll(result);
            log.info("세관장확인대상 {}건 저장 완료 (hsCode={})", result.size(), hsCode);
            return true;
        } catch (Exception e) {
            log.error("세관장확인대상 파싱 실패 (hsCode={}): {}", hsCode, e.getMessage());
            return false;
        }
    }

    /**
     * XML 노드 하나를 CustomsConfirmation 엔티티로 변환한다.
     * @param node 세관장확인대상물품 XML 노드
     * @return CustomsConfirmation 엔티티
     */
    private CustomsConfirmation parseConfirmation(JsonNode node) {
        LocalDate applyStartDate = parseDate(node.path("aplyStrtDt").asText(""));

        return CustomsConfirmation.fromApi(
                node.path("hsSgn").asText(""),              // 품목코드
                node.path("bfhnAffcRtmTpcd").asText(""),    // 수출입구분
                node.path("dcerCfrmLworNm").asText(""),     // 근거법령명
                node.path("reqApreIttNm").asText(""),       // 요건확인기관명
                node.path("reqCfrmIstmNm").asText(""),      // 구비서류명
                applyStartDate
        );
    }

    /**
     * "yyyyMMdd" 형식의 날짜 문자열을 LocalDate로 변환한다.
     * @param dateStr 날짜 문자열
     * @return LocalDate 또는 빈 값이면 null
     */
    private LocalDate parseDate(String dateStr) {
        if (dateStr.isBlank()) return null;
        return LocalDate.parse(dateStr, DATE_FORMAT);
    }
}
