package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import java.util.List;

import org.hamcrest.Matchers;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import java.nio.charset.StandardCharsets;

import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.Law;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.LawArticle;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.LawArticleRepository;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.LawRepository;

@ExtendWith(MockitoExtension.class)
class LawApiClientTest {

    @Mock
    private LawRepository lawRepository;

    @Mock
    private LawArticleRepository lawArticleRepository;

    private MockRestServiceServer server;
    private LawApiClient lawApiClient;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();
        lawApiClient = new LawApiClient(restClient, lawRepository, lawArticleRepository);
    }

    @Test
    @DisplayName("법령 검색 결과가 있으면 Law와 LawArticle을 저장하고 true를 반환한다.")
    void fetchAndSave_withResults_thenSaveLawsAndArticles() {
        // given
        String searchXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <LawSearch>
                    <totalCnt>1</totalCnt>
                    <law>
                        <법령일련번호>270323</법령일련번호>
                        <법령ID>002015</법령ID>
                        <법령명한글>화장품법</법령명한글>
                        <법령약칭명></법령약칭명>
                        <법령구분명>법률</법령구분명>
                        <시행일자>20260402</시행일자>
                        <소관부처명>식품의약품안전처</소관부처명>
                        <현행연혁코드>현행</현행연혁코드>
                    </law>
                </LawSearch>
                """;

        String serviceXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <법령>
                    <조문>
                        <조문단위>
                            <조문여부>조문</조문여부>
                            <조문번호>1</조문번호>
                            <조문가지번호>0</조문가지번호>
                            <조문제목>목적</조문제목>
                            <조문내용>제1조(목적) 이 법은 테스트입니다.</조문내용>
                            <조문시행일자>20260402</조문시행일자>
                        </조문단위>
                    </조문>
                </법령>
                """;

        given(lawRepository.saveAll(anyList())).willAnswer(inv -> inv.getArgument(0));

        server.expect(requestTo(Matchers.containsString("lawSearch.do")))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(searchXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));

        server.expect(requestTo(Matchers.containsString("MST=270323")))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(serviceXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));

        // when
        boolean result = lawApiClient.fetchAndSave("test");

        // then
        assertThat(result).isTrue();
        server.verify();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<Law>> lawCaptor = ArgumentCaptor.forClass(List.class);
        then(lawRepository).should().saveAll(lawCaptor.capture());
        assertThat(lawCaptor.getValue()).hasSize(1);
        assertThat(lawCaptor.getValue().get(0).getNameKo()).isEqualTo("화장품법");
        assertThat(lawCaptor.getValue().get(0).getLawMst()).isEqualTo("270323");
        assertThat(lawCaptor.getValue().get(0).getIsCurrent()).isTrue();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<LawArticle>> articleCaptor = ArgumentCaptor.forClass(List.class);
        then(lawArticleRepository).should().saveAll(articleCaptor.capture());
        assertThat(articleCaptor.getValue()).hasSize(1);
        assertThat(articleCaptor.getValue().get(0).getTitle()).isEqualTo("목적");
        assertThat(articleCaptor.getValue().get(0).getArticleNo()).isEqualTo(1);
    }

    @Test
    @DisplayName("법령 검색 결과가 없으면 false를 반환하고 저장하지 않는다.")
    void fetchAndSave_withNoResults_thenReturnFalse() {
        // given
        String emptyXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <LawSearch><totalCnt>0</totalCnt></LawSearch>
                """;

        server.expect(requestTo(Matchers.containsString("lawSearch.do")))
                .andRespond(withSuccess(emptyXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));

        // when
        boolean result = lawApiClient.fetchAndSave("없는법");

        // then
        assertThat(result).isFalse();
        then(lawRepository).should(never()).saveAll(anyList());
    }

    @Test
    @DisplayName("조문여부가 '전문'인 항목은 건너뛰고 '조문'만 저장한다.")
    void fetchAndSave_thenSkipNonArticle() {
        // given
        String searchXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <LawSearch>
                    <law>
                        <법령일련번호>100000</법령일련번호>
                        <법령ID>000001</법령ID>
                        <법령명한글>테스트법</법령명한글>
                        <법령약칭명></법령약칭명>
                        <법령구분명>법률</법령구분명>
                        <시행일자>20260101</시행일자>
                        <소관부처명>테스트부처</소관부처명>
                        <현행연혁코드>현행</현행연혁코드>
                    </law>
                </LawSearch>
                """;

        String serviceXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <법령>
                    <조문>
                        <조문단위>
                            <조문여부>전문</조문여부>
                            <조문번호>0</조문번호>
                            <조문내용>전문개정 내용</조문내용>
                        </조문단위>
                        <조문단위>
                            <조문여부>조문</조문여부>
                            <조문번호>1</조문번호>
                            <조문가지번호>0</조문가지번호>
                            <조문제목>목적</조문제목>
                            <조문내용>제1조(목적)</조문내용>
                            <조문시행일자>20260101</조문시행일자>
                        </조문단위>
                    </조문>
                </법령>
                """;

        given(lawRepository.saveAll(anyList())).willAnswer(inv -> inv.getArgument(0));

        server.expect(requestTo(Matchers.containsString("lawSearch.do")))
                .andRespond(withSuccess(searchXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));
        server.expect(requestTo(Matchers.containsString("MST=100000")))
                .andRespond(withSuccess(serviceXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));

        // when
        lawApiClient.fetchAndSave("테스트");

        // then
        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<LawArticle>> captor = ArgumentCaptor.forClass(List.class);
        then(lawArticleRepository).should().saveAll(captor.capture());
        assertThat(captor.getValue()).hasSize(1);
        assertThat(captor.getValue().get(0).getTitle()).isEqualTo("목적");
    }
}
