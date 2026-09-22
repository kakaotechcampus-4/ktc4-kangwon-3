package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.BatchSize;

import java.util.ArrayList;
import java.util.List;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "product",
        indexes = @Index(name = "idx_product_diagnoses_id_sort_order", columnList = "diagnoses_id, sort_order")
)
public class Product extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "product_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "diagnoses_id", nullable = false)
    private Diagnoses diagnoses;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    @Column(name = "product_name", nullable = false)
    private String productName;

    @Enumerated(EnumType.STRING)
    @Column(name = "source_type", nullable = false)
    private SourceType sourceType;

    @Column(name = "source_url", columnDefinition = "TEXT")
    private String sourceUrl;

    @Column(name = "source_text", columnDefinition = "TEXT")
    private String sourceText;

    @Enumerated(EnumType.STRING)
    @Column(name = "processing_status", nullable = false)
    private ProcessingStatus processingStatus;

    @Enumerated(EnumType.STRING)
    @Column(name = "result_status")
    private ResultStatus resultStatus;

    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;

    @Column(name = "product_image_key", columnDefinition = "TEXT")
    private String productImageKey;

    // 진단서 -> 상품을 fetch join한 뒤 상품별 이미지를 지연 로딩할 때 쿼리가 N번 나가는 것을 막는다.
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    @BatchSize(size = 100)
    private List<ProductImage> images = new ArrayList<>();

    @Builder(access = AccessLevel.PRIVATE)
    private Product(String productName, String productImageKey,
                    SourceType sourceType, String sourceUrl, String sourceText) {
        this.productName = productName;
        this.productImageKey = productImageKey;
        this.sourceType = sourceType;
        this.sourceUrl = sourceUrl;
        this.sourceText = sourceText;
        this.processingStatus = ProcessingStatus.PENDING;
    }

    public static Product pending(String productName, String productImageKey,
                                  SourceType sourceType, String sourceUrl, String sourceText) {
        return Product.builder()
                .productName(productName)
                .productImageKey(productImageKey)
                .sourceType(sourceType)
                .sourceUrl(sourceUrl)
                .sourceText(sourceText)
                .build();
    }

    public void addImages(List<String> imageKeys) {
        for (String imageKey : imageKeys) {
            images.add(new ProductImage(this, imageKey, images.size()));
        }
    }

    // Diagnoses.addProducts 에서만 호출한다. 상품은 진단서를 거쳐서만 연결되어야 한다.
    void assignTo(Diagnoses diagnoses, int sortOrder) {
        this.diagnoses = diagnoses;
        this.sortOrder = sortOrder;
    }
}
