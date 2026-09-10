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
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.MedicalDevice;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.MedicalDeviceRepository;

@ExtendWith(MockitoExtension.class)
class MedicalDeviceApiClientTest {

    @Mock
    private MedicalDeviceRepository medicalDeviceRepository;

    private MockRestServiceServer server;
    private MedicalDeviceApiClient medicalDeviceApiClient;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();
        medicalDeviceApiClient = new MedicalDeviceApiClient(restClient, medicalDeviceRepository);
        ReflectionTestUtils.setField(medicalDeviceApiClient, "serviceKey", "test-key");
    }

    @Test
    @DisplayName("의료기기 품목 조회 결과가 있으면 저장하고 true를 반환한다.")
    void fetchAndSave_withResults_thenSaveAndReturnTrue() {
        // given
        String responseJson = """
                {
                    "header": {"resultCode": "00"},
                    "body": {
                        "totalCount": 1,
                        "items": [
                            {
                                "item": {
                                    "MDEQ_PRDLST_SN": "106",
                                    "PRDLST_NM": "체외형 범용 프로브",
                                    "MDEQ_CLSF_NO": "A58020.01",
                                    "CLSF_NO_GRAD_CD": "1",
                                    "PRMSN_DCLR_DIVS_NM": "신고",
                                    "INDT_NM": "제조업",
                                    "USE_PURPS_CONT": "신호를 전달하는 기구"
                                }
                            }
                        ]
                    }
                }
                """;

        server.expect(requestTo(Matchers.containsString("MdeqPrdlstInfoService02")))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseJson, MediaType.APPLICATION_JSON));

        // when
        boolean result = medicalDeviceApiClient.fetchAndSave(1, 10);

        // then
        assertThat(result).isTrue();
        server.verify();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<MedicalDevice>> captor = ArgumentCaptor.forClass(List.class);
        then(medicalDeviceRepository).should().saveAll(captor.capture());
        assertThat(captor.getValue()).hasSize(1);
        assertThat(captor.getValue().get(0).getDeviceSn()).isEqualTo("106");
        assertThat(captor.getValue().get(0).getProductName()).isEqualTo("체외형 범용 프로브");
        assertThat(captor.getValue().get(0).getGrade()).isEqualTo("1");
    }

    @Test
    @DisplayName("조회 결과가 없으면 false를 반환하고 저장하지 않는다.")
    void fetchAndSave_withEmptyItems_thenReturnFalse() {
        // given
        String emptyJson = """
                {
                    "header": {"resultCode": "00"},
                    "body": {"totalCount": 0, "items": []}
                }
                """;

        server.expect(requestTo(Matchers.containsString("MdeqPrdlstInfoService02")))
                .andRespond(withSuccess(emptyJson, MediaType.APPLICATION_JSON));

        // when
        boolean result = medicalDeviceApiClient.fetchAndSave(1, 10);

        // then
        assertThat(result).isFalse();
        then(medicalDeviceRepository).should(never()).saveAll(anyList());
    }
}
