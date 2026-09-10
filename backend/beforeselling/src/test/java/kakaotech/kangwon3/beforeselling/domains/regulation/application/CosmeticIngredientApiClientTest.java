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

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.CosmeticIngredient;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.CosmeticIngredientRepository;

@ExtendWith(MockitoExtension.class)
class CosmeticIngredientApiClientTest {

    @Mock
    private CosmeticIngredientRepository cosmeticIngredientRepository;

    private MockRestServiceServer server;
    private CosmeticIngredientApiClient cosmeticIngredientApiClient;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();
        cosmeticIngredientApiClient = new CosmeticIngredientApiClient(restClient, cosmeticIngredientRepository);
        ReflectionTestUtils.setField(cosmeticIngredientApiClient, "serviceKey", "test-key");
    }

    @Test
    @DisplayName("화장품 규제원료 조회 결과가 있으면 저장하고 true를 반환한다.")
    void fetchAndSave_withResults_thenSaveAndReturnTrue() {
        // given
        String responseJson = """
                {
                    "header": {"resultCode": "00"},
                    "body": {
                        "totalCount": 2,
                        "items": [
                            {
                                "INGR_STD_NAME": "트라이메틸아닐린",
                                "INGR_ENG_NAME": "Trimethylaniline",
                                "PROH_NATIONAL": "EU,한국",
                                "LIMIT_NATIONAL": null
                            },
                            {
                                "INGR_STD_NAME": "코코트라이모늄클로라이드",
                                "INGR_ENG_NAME": "Cocotrimonium Chloride",
                                "PROH_NATIONAL": null,
                                "LIMIT_NATIONAL": "EU,한국"
                            }
                        ]
                    }
                }
                """;

        server.expect(requestTo(Matchers.containsString("CsmtcsReglMaterialInfoService")))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(responseJson, MediaType.APPLICATION_JSON));

        // when
        boolean result = cosmeticIngredientApiClient.fetchAndSave(1, 10);

        // then
        assertThat(result).isTrue();
        server.verify();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<CosmeticIngredient>> captor = ArgumentCaptor.forClass(List.class);
        then(cosmeticIngredientRepository).should().saveAll(captor.capture());
        assertThat(captor.getValue()).hasSize(2);
        assertThat(captor.getValue().get(0).getIngredientNameKo()).isEqualTo("트라이메틸아닐린");
        assertThat(captor.getValue().get(0).getProhibitedCountries()).isEqualTo("EU,한국");
        assertThat(captor.getValue().get(1).getLimitedCountries()).isEqualTo("EU,한국");
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

        server.expect(requestTo(Matchers.containsString("CsmtcsReglMaterialInfoService")))
                .andRespond(withSuccess(emptyJson, MediaType.APPLICATION_JSON));

        // when
        boolean result = cosmeticIngredientApiClient.fetchAndSave(1, 10);

        // then
        assertThat(result).isFalse();
        then(cosmeticIngredientRepository).should(never()).saveAll(anyList());
    }
}
