package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UuidGenerator;
import java.util.UUID;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "product_image",
        indexes = @Index(name = "idx_product_image_product_id", columnList = "product_id")
)
public class ProductImage extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "product_image_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @Column(name = "image_key", nullable = false, columnDefinition = "TEXT")
    private String imageKey;

    // BE -> AI OCR 깨짐 방지를 위하여
    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    ProductImage(Product product, String imageKey, int sortOrder) {
        this.product = product;
        this.imageKey = imageKey;
        this.sortOrder = sortOrder;
    }
}