package kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity;

import java.time.OffsetDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.Builder;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "cosmetic_ingredients")
public class CosmeticIngredient {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "cosmetic_ingredient_id")
    private Long id;

    @Column(name = "ingredient_name_ko", length = 500, nullable = false)
    private String ingredientNameKo;

    @Column(name = "ingredient_name_en", length = 500)
    private String ingredientNameEn;

    @Column(name = "prohibited_countries", length = 200)
    private String prohibitedCountries;

    @Column(name = "limited_countries", length = 200)
    private String limitedCountries;

    @Column(name = "fetched_at", nullable = false)
    private OffsetDateTime fetchedAt;

    @Builder(access = AccessLevel.PRIVATE)
    private CosmeticIngredient(String ingredientNameKo,
                               String ingredientNameEn,
                               String prohibitedCountries,
                               String limitedCountries,
                               OffsetDateTime fetchedAt) {
        this.ingredientNameKo = ingredientNameKo;
        this.ingredientNameEn = ingredientNameEn;
        this.prohibitedCountries = prohibitedCountries;
        this.limitedCountries = limitedCountries;
        this.fetchedAt = fetchedAt;
    }

    public static CosmeticIngredient fromApi(String ingredientNameKo,
                                             String ingredientNameEn,
                                             String prohibitedCountries,
                                             String limitedCountries) {
        return CosmeticIngredient.builder()
                .ingredientNameKo(ingredientNameKo)
                .ingredientNameEn(ingredientNameEn)
                .prohibitedCountries(prohibitedCountries)
                .limitedCountries(limitedCountries)
                .fetchedAt(OffsetDateTime.now())
                .build();
    }
}