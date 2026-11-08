package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.OnDelete;
import org.hibernate.annotations.OnDeleteAction;
import org.hibernate.annotations.UuidGenerator;

import java.util.UUID;

// 법령 변경으로 다시 확인해야 하는 상품. 재진단하거나 상품을 지우면 삭제됨.
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "law_amendment_product",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_law_amendment_product_law_amendment_id_product_id",
                columnNames = {"law_amendment_id", "product_id"}
        )
)
public class LawAmendmentProduct extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "law_amendment_product_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "law_amendment_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    private LawAmendment lawAmendment;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    @OnDelete(action = OnDeleteAction.CASCADE)
    private Product product;

    private LawAmendmentProduct(LawAmendment lawAmendment, Product product) {
        this.lawAmendment = lawAmendment;
        this.product = product;
    }

    public static LawAmendmentProduct of(LawAmendment lawAmendment, Product product) {
        return new LawAmendmentProduct(lawAmendment, product);
    }
}
