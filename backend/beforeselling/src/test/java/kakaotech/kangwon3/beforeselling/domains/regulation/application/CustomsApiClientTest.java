package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyList;
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
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.CustomsConfirmation;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.CustomsConfirmationRepository;

@ExtendWith(MockitoExtension.class)
class CustomsApiClientTest {

    @Mock
    private CustomsConfirmationRepository customsConfirmationRepository;

    private MockRestServiceServer server;
    private CustomsApiClient customsApiClient;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();
        customsApiClient = new CustomsApiClient(restClient, customsConfirmationRepository);
        ReflectionTestUtils.setField(customsApiClient, "serviceKey", "test-key");
    }

    @Test
    @DisplayName("세관장확인대상 조회 결과가 있으면 저장하고 true를 반환한다.")
    void fetchAndSave_withResults_thenSaveAndReturnTrue() {
        // given
        String responseXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <response>
                    <header><resultCode>00</resultCode></header>
                    <body>
                        <items>
                            <item>
                                <hsSgn>3304990000</hsSgn>
                                <bfhnAffcRtmTpcd>2</bfhnAffcRtmTpcd>
                                <dcerCfrmLworNm>화장품법</dcerCfrmLworNm>
                                <reqApreIttNm>식품의약품안전처</reqApreIttNm>
                                <reqCfrmIstmNm>화장품제조판매업등록필증</reqCfrmIstmNm>
                                <aplyStrtDt>20200101</aplyStrtDt>
                            </item>
                        </items>
                    </body>
                </response>
                """;

        server.expect(requestTo(Matchers.containsString("retrieveCcctLworCd")))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));

        // when
        boolean result = customsApiClient.fetchAndSave("3304990000", "2");

        // then
        assertThat(result).isTrue();
        server.verify();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<CustomsConfirmation>> captor = ArgumentCaptor.forClass(List.class);
        then(customsConfirmationRepository).should().saveAll(captor.capture());
        assertThat(captor.getValue()).hasSize(1);
        assertThat(captor.getValue().get(0).getHsCode()).isEqualTo("3304990000");
        assertThat(captor.getValue().get(0).getLawName()).isEqualTo("화장품법");
        assertThat(captor.getValue().get(0).getAgencyName()).isEqualTo("식품의약품안전처");
    }

    @Test
    @DisplayName("조회 결과가 없으면 false를 반환하고 저장하지 않는다.")
    void fetchAndSave_withEmptyItems_thenReturnFalse() {
        // given
        String emptyXml = """
                <?xml version="1.0" encoding="UTF-8"?>
                <response>
                    <header><resultCode>00</resultCode></header>
                    <body><items/></body>
                </response>
                """;

        server.expect(requestTo(Matchers.containsString("retrieveCcctLworCd")))
                .andRespond(withSuccess(emptyXml, new MediaType("application", "xml", StandardCharsets.UTF_8)));

        // when
        boolean result = customsApiClient.fetchAndSave("9999", "2");

        // then
        assertThat(result).isFalse();
        then(customsConfirmationRepository).should(never()).saveAll(anyList());
    }
}
