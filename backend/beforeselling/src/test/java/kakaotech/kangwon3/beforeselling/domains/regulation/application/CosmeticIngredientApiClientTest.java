package kakaotech.kangwon3.beforeselling.domains.regulation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;

import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.CosmeticIngredient;
import kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository.CosmeticIngredientRepository;
import kakaotech.kangwon3.beforeselling.global.util.DataGoKrApiCaller;

@ExtendWith(MockitoExtension.class)
class CosmeticIngredientApiClientTest {

    @Mock
    private DataGoKrApiCaller apiCaller;

    @Mock
    private CosmeticIngredientRepository cosmeticIngredientRepository;

    @InjectMocks
    private CosmeticIngredientApiClient cosmeticIngredientApiClient;

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

        given(apiCaller.call(
                eq("https://apis.data.go.kr/1471000/CsmtcsReglMaterialInfoService/getCsmtcsReglMaterialInfoService"),
                startsWith("pageNo=1")))
                .willReturn(responseJson);

        // when
        boolean result = cosmeticIngredientApiClient.fetchAndSave(1, 10);

        // then
        assertThat(result).isTrue();

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

        given(apiCaller.call(
                eq("https://apis.data.go.kr/1471000/CsmtcsReglMaterialInfoService/getCsmtcsReglMaterialInfoService"),
                startsWith("pageNo=1")))
                .willReturn(emptyJson);

        // when
        boolean result = cosmeticIngredientApiClient.fetchAndSave(1, 10);

        // then
        assertThat(result).isFalse();
        then(cosmeticIngredientRepository).should(never()).saveAll(anyList());
    }
}
