package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.Law;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.LawArticle;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.LawRepository;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.LawArticleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class LawApiClient {

    private static final String SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do";
    private static final String SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do";
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final RestClient restClient;
    private final LawRepository lawRepository;
    private final LawArticleRepository lawArticleRepository;
    private final XmlMapper xmlMapper = new XmlMapper();

    /**
     * 법령 검색과 그 법안들의 본문을 수집을 진행한다.
     * @param query 검색할 법령명
     * @return 저장 성공 여부
     */
    public boolean fetchAndSave(String query) {

        // 법령을 검색하여 리스트에 담음
        List<Law> laws = fetchLaws(query);

        if (laws.isEmpty()) {
            return false;
        }

        // 법령들의 본문을 for문을 통해 가져옴
        for (Law law : laws) {
            fetchArticles(law);
        }

        return true;
    }

    /**
     * 법령검색 API를 호출하여 법령 메타데이터를 저장한다.
     * @param query 검색할 법령명
     * @return 저장된 Law 엔티티 목록
     */
    private List<Law> fetchLaws(String query) {

        // RestClient를 통해 GET 요청하여 응답받은 XML을 저장
        String xml = restClient.get()
                .uri(SEARCH_URL + "?OC=test&target=law&type=XML&display=100&query=" + query)
                .retrieve()
                .body(String.class);

        // 응답받은 XML을 Law 엔티티로 가공
        List<Law> result = new ArrayList<>();
        try {
            JsonNode root = xmlMapper.readTree(xml);
            JsonNode laws = root.path("law");

            // 검색 결과가 없을 때
            if (laws.isMissingNode()) {
                return List.of();
            }

            // 결과가 2건 이상이면 배열, 1건이면 단일 객체
            if (laws.isArray()) {
                for (JsonNode node : laws) {
                    result.add(parseLaw(node));
                }
            } else {
                result.add(parseLaw(laws));
            }

            lawRepository.saveAll(result);
            log.info("법령 {}건 저장 완료 (query={})", result.size(), query);
        } catch (Exception e) {
            log.error("법령검색 파싱 실패: {}", e.getMessage());
            return List.of();
        }
        return result;
    }

    /**
     * 법령본문 API를 호출하여 조문 텍스트를 저장한다.
     * @param law 조문을 가져올 법령
     * @return 저장된 LawArticle 엔티티 목록
     */
    private List<LawArticle> fetchArticles(Law law) {

        // RestClient를 통해 GET 요청하여 응답받은 XML을 저장
        String xml = restClient.get()
                .uri(SERVICE_URL + "?OC=test&target=law&MST=" + law.getLawMst() + "&type=XML")
                .retrieve()
                .body(String.class);

        // 응답받은 XML을 List<LawArticle>로 가공
        try {
            JsonNode root = xmlMapper.readTree(xml);
            JsonNode articles = root.path("조문").path("조문단위");

            // 조문이 없는 법령일 때
            if (articles.isMissingNode()) {
                return List.of();
            }

            List<LawArticle> result = new ArrayList<>();

            // 조문이 2건 이상
            if (articles.isArray()) {
                for (JsonNode node : articles) {
                    // 조문 여부가 "전문(전문개정문)"일 때는 스킵
                    if (!"조문".equals(node.path("조문여부").asText())) continue;
                    result.add(parseArticle(law, node));
                }
            } else {
                // 조문이 1건일 때
                if ("조문".equals(articles.path("조문여부").asText())) {
                    result.add(parseArticle(law, articles));
                }
            }

            lawArticleRepository.saveAll(result);
            log.info("법령 [{}] 조문 {}건 저장 완료", law.getNameKo(), result.size());
            return result;
        } catch (Exception e) {
            log.error("법령본문 파싱 실패 (MST={}): {}", law.getLawMst(), e.getMessage());
            return List.of();
        }
    }

    /**
     * XML 노드 하나를 Law 엔티티로 변환한다.
     * @param node 법령 XML 노드
     * @return Law 엔티티
     */
    private Law parseLaw(JsonNode node) {
        String enforceDateStr = node.path("시행일자").asText("");
        LocalDate enforceDate = enforceDateStr.isBlank() ? null
                : LocalDate.parse(enforceDateStr, DATE_FORMAT);

        String currentCode = node.path("현행연혁코드").asText("");
        boolean isCurrent = "현행".equals(currentCode);

        return Law.fromApi(
                node.path("법령일련번호").asText(),
                node.path("법령ID").asText(),
                node.path("법령명한글").asText(),
                node.path("법령약칭명").asText(""),
                node.path("법령구분명").asText(),
                enforceDate,
                node.path("소관부처명").asText(""),
                isCurrent
        );
    }

    /**
     * XML 노드 하나를 LawArticle 엔티티로 변환한다.
     * 항·호 내용을 합쳐 fullText를 구성한다.
     * @param law 소속 법령
     * @param node 조문 XML 노드
     * @return LawArticle 엔티티
     */
    private LawArticle parseArticle(Law law, JsonNode node) {
        String enforceDateStr = node.path("조문시행일자").asText("");
        LocalDate enforceDate = enforceDateStr.isBlank() ? null
                : LocalDate.parse(enforceDateStr, DATE_FORMAT);

        Integer articleNo = node.path("조문번호").asInt(0);
        Integer articleBranch = node.path("조문가지번호").asInt(0);

        // 가지번호가 없으면 0으로 파싱, DB에는 null로 저장
        if (articleBranch == 0) articleBranch = null;

        // 조문내용 + 항내용 + 호내용을 합쳐 fullText 구성
        String content = node.path("조문내용").asText("");
        StringBuilder fullText = new StringBuilder(content);

        JsonNode hangs = node.path("항");
        if (hangs.isArray()) {
            for (JsonNode hang : hangs) {
                fullText.append("\n").append(hang.path("항내용").asText(""));
                JsonNode hos = hang.path("호");
                if (hos.isArray()) {
                    for (JsonNode ho : hos) {
                        fullText.append("\n  ").append(ho.path("호내용").asText(""));
                    }
                }
            }
        }

        return LawArticle.fromApi(
                law,
                articleNo,
                articleBranch,
                node.path("조문제목").asText(""),
                fullText.toString(),
                enforceDate
        );
    }
}
